#!/usr/bin/env python

import asyncio
import argparse
import json
import logging
import os
import uuid
from pprint import pprint

from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException

from nats.aio.client import Client as NATS
from stan.aio.client import Client as STAN
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers

parser = argparse.ArgumentParser()
# Kubernetes related arguments
parser.add_argument('--in-cluster', help="use in cluster kubernetes config", action="store_true", default=True) # "default=False" if running locally
parser.add_argument('--pretty', help='Output pretty printed.', default=False)
parser.add_argument('-t', '--topic', help="NATS Streaming topic", default="k8s_ingresses")
# parser.add_argument('--dry-run', help='Indicates that modifications should not be persisted. Valid values are: - All: all dry run stages will be processed (optional)')
# NATS releated arguments
parser.add_argument('-a', '--nats-address', help="address of nats cluster", default=os.environ.get('NATS_ADDRESS', None))
parser.add_argument('-c', '--stan-cluster', help="STAN cluster name", default=os.environ.get('STAN_CLUSTER', None))

parser.add_argument('--connect-timeout', help="NATS connect timeout (s)", type=int, default=10, dest='conn_timeout')
parser.add_argument('--max-reconnect-attempts', help="number of times to attempt reconnect", type=int, default=5, dest='conn_attempts')
parser.add_argument('--reconnect-time-wait', help="how long to wait between reconnect attempts", type=int, default=1, dest='conn_wait')

# Logger arguments
parser.add_argument('-d', '--debug', help="enable debug logging", action="store_true")
parser.add_argument('--output-deployments', help="output all deployments to stdout", action="store_true", dest='enable_output')
args = parser.parse_args()

logger = logging.getLogger('script')
ch = logging.StreamHandler()
if args.debug:
    logger.setLevel(logging.DEBUG)
    ch.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)
    ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)


if args.in_cluster:
    config.load_incluster_config()
else:
    try:
        config.load_kube_config()
    except Exception as e:
        logger.critical("Error creating Kubernetes configuration: %s", e)
        exit(2)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def handle(req):
    payload = json.loads(req)

    # Client to list Services
    CoreV1Api = client.CoreV1Api()
    
    # Client to list Ingresses
    ExtensionsV1beta1Api = client.ExtensionsV1beta1Api()

    # Client to Manage Web-Rescale deployment
    AppsV1Api = client.AppsV1Api()

    # Service patches
    serviceName = '[{"op": "replace", "path": "/spec/rules/0/http/paths/0/backend/serviceName", "value": "web-activate"}]'
    servicePort = '[{"op": "replace", "path": "/spec/rules/0/http/paths/0/backend/servicePort", "value": 80}]'

    # Convert labels to key=value array of string (e.g. key1=value1,key2=value2) 
    list=[]
    print(payload['labels'])
    for key, value in payload["labels"].items():
        temp = key + "=" + value
        list.append(temp)
    label_selector = ','.join(list)

    # Search for service that use the Selector
    try:
        logger.info("Searching for Service (svc) in Namespace: %s with Labels: %s" % (payload['namespace'], label_selector))
        
        services = CoreV1Api.list_namespaced_service(namespace=payload['namespace'], label_selector=label_selector, pretty=args.pretty)
    except ApiException as e:
        print("Exception when calling CoreV1Api->list_namespaced_service: %s\n" % e)
        print(payload.keys())
        print(type(payload))
        print(str(payload))

    try:
        # Search for in Ingresses configured with the Service Name
        for service in services.items:
            logger.info("Searching for Ingress (ing) in Namespace: %s with Bakend: %s" % (payload['namespace'], service.metadata.name))
            
            ingresses = ExtensionsV1beta1Api.list_namespaced_ingress(namespace=payload['namespace'], pretty=args.pretty)
            #pprint(ingresses)

            for ingress in ingresses.items:
                logger.info("Searching for Ingress Backend: %s in Ingress: %s" % (service.metadata.name, ingress.metadata.name))
                rule_index = 0
                for rule in ingress.spec.rules:
                    path_index = 0
                    for path in rule.http.paths:
                        if path.backend.service_name == service.metadata.name:
                            logger.info("Found Service name: %s Port: %s in Ingress: %s" % (path.backend.service_name, path.backend.service_port, ingress.metadata.name))
                            logger.info("Patching Ingress name:%s with Service name: %s with Port: %s" % (ingress.metadata.name, path.backend.service_name, path.backend.service_port))
                            
                            body = [
                                {"op": "replace", "path": "/spec/rules/" + str(rule_index) + "/http/paths/" + str(path_index) + "/backend/serviceName", "value": "web-reactivate"},
                                {"op": "replace", "path": "/spec/rules/" + str(rule_index) + "/http/paths/" + str(path_index) + "/backend/servicePort", "value": 3000}
                            ]
                            
                            try: 
                                logger.debug("Patch specifications: %s" %(json.loads(json.dumps(body))))

                                patch_ingress = ExtensionsV1beta1Api.patch_namespaced_ingress(name=ingress.metadata.name, namespace=ingress.metadata.namespace, body=json.loads(json.dumps(body)), pretty=args.pretty)
                            except ApiException as e:
                                print("Exception when calling ExtensionsV1beta1Api->patch_namespaced_ingress: %s\n" % e)
                                print(payload.keys())
                                print(type(payload))
                                print(str(payload))

                        path_index += 1
                    rule_index +=1
                 
                loop.run_until_complete(publish(json.loads(ingress.metadata.annotations["kubectl.kubernetes.io/last-applied-configuration"]), loop))
    except ApiException as e:
        print("Exception when calling ExtensionsV1beta1Api->list_namespaced_ingress: %s\n" % e)
        print(payload.keys())
        print(type(payload))
        print(str(payload))

async def publish(ingress_resource, loop):
    # Use borrowed connection for NATS then mount NATS Streaming
    # client on top.
    nc = NATS()
    
    # Start session with NATS Streaming cluster.
    sc = STAN()

    try:
        await nc.connect(args.nats_address, loop=loop,connect_timeout=args.conn_timeout, max_reconnect_attempts=args.conn_attempts, reconnect_time_wait=args.conn_wait)
        await sc.connect(args.stan_cluster, "publish-ingress-" + str(uuid.uuid4()), nats=nc)
    except ErrNoServers as e:
        # Could not connect to any server in the cluster.
        print(e)
        return

    total_messages = 0
    future = asyncio.Future(loop=loop)
    async def cb(msg):
        nonlocal future
        nonlocal total_messages
        print("Received a message (seq={}): {}".format(msg.seq, msg.data))
        total_messages += 1
        if total_messages >= 2:
            future.set_result(None)
            
    # Subscribe to get all messages since beginning.
    sub = await sc.subscribe(args.topic, start_at='first', cb=cb)
    await asyncio.wait_for(future, 1, loop=loop)
    
    msg = {"namespace": ingress_resource["metadata"]["namespace"], "name": ingress_resource["metadata"]["name"], "rules": ingress_resource["spec"]["rules"] }

    try:
        # STAN publish
        await sc.publish(args.topic, json.dumps(msg).encode('utf-8'), ack_handler=True)
    except ErrConnectionClosed as e:
        print("Connection closed prematurely.")
    except ErrTimeout as e:
        print("Timeout occured when publishing msg i={}: {}".format(deploy, e))

    await sc.close()

# Used only for local testing
if __name__ == '__main__':
    req = '{"namespace": "demo", "name": "web", "kind": "statefulset", "replicas": 3, "labels": {"app": "nginx", "type": "statefulset"}}'
    handle(req)
