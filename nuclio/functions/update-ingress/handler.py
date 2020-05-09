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
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers

output = {"data":[]}

parser = argparse.ArgumentParser()
# Function related arguments
parser.add_argument('-t', '--topic', help="NATS Streaming topic", default="k8s_ingresses")
# Kubernetes related arguments
parser.add_argument('--in-cluster', help="Use in cluster kubernetes config", action="store_true", default=True) # "default=False" if running locally
parser.add_argument('--pretty', help='Output pretty printed.', default=False)
# NATS releated arguments
parser.add_argument('-a', '--nats-address', help="Address of nats cluster", default=os.environ.get('NATS_ADDRESS', None))
parser.add_argument('--connect-timeout', help="NATS connect timeout (s)", type=int, default=10, dest='conn_timeout')
parser.add_argument('--max-reconnect-attempts', help="Number of times to attempt reconnect", type=int, default=5, dest='conn_attempts')
parser.add_argument('--reconnect-time-wait', help="How long to wait between reconnect attempts", type=int, default=1, dest='conn_wait')
# Logger arguments
parser.add_argument('-d', '--debug', help="Enable debug logging", action="store_true")
args, unknown = parser.parse_known_args()

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

def handle(context, event):
    payload = json.loads(event.body)

    # Client to list Services
    CoreV1Api = client.CoreV1Api()
    
    # Client to list Ingresses
    ExtensionsV1beta1Api = client.ExtensionsV1beta1Api()

    # Client to Manage Web-Rescale deployment
    AppsV1Api = client.AppsV1Api()

    # Convert labels to key=value array of string (e.g. key1=value1,key2=value2) 
    array=[]

    for key, value in payload["labels"].items():
        temp = key + "=" + value
        array.append(temp)
    label_selector = ','.join(array)
    pprint(label_selector)

    # Search for service that use the Selector
    try:
        logger.debug("Searching for Service (svc) in Namespace: %s with Labels: %s" % (payload['namespace'], label_selector))
        
        services = CoreV1Api.list_namespaced_service(namespace=payload['namespace'], label_selector=label_selector, pretty=args.pretty)
    except ApiException as e:
        print("Exception when calling CoreV1Api->list_namespaced_service: %s\n" % e)
        print(payload.keys())
        print(type(payload))
        print(str(payload))

    try:
        # Search for in Ingresses configured with the Service Name
        for service in services.items:
            logger.debug("Searching for Ingress (ing) in Namespace: %s with Bakend: %s" % (payload['namespace'], service.metadata.name))
            
            ingresses = ExtensionsV1beta1Api.list_namespaced_ingress(namespace=payload['namespace'], pretty=args.pretty)

            for ingress in ingresses.items:
                logger.debug("Searching for Ingress Backend: %s in Ingress: %s" % (service.metadata.name, ingress.metadata.name))
                rule_index = 0
                for rule in ingress.spec.rules:
                    path_index = 0
                    for path in rule.http.paths:
                        if path.backend.service_name == service.metadata.name:
                            logger.info("Found Service name: %s Port: %s in Ingress: %s" % (path.backend.service_name, path.backend.service_port, ingress.metadata.name))
                            logger.debug("Patching Ingress name: %s containing service Name: %s with Port: %s" % (ingress.metadata.name, path.backend.service_name, path.backend.service_port))
                            
                            # Backup current rules if "kubectl.kubernetes.io/last-applied-configuration" annotation does not exist
                            if not "kubectl.kubernetes.io/last-applied-configuration" in ingress.metadata.annotations:
                                annotation = {
                                    "metadata": {
                                        "annotations": {
                                            "rules.nozzle.io/last-known-configuration": json.dumps(client.ApiClient().sanitize_for_serialization(ingress.spec.rules), indent=None)
                                        }
                                    }
                                }

                                logger.debug("Backing up rules of Ingress (ing) Name: %s to %s" % (ingress.metadata.name, annotation))
                                try:
                                    backup_rules = ExtensionsV1beta1Api.patch_namespaced_ingress(name=ingress.metadata.name, namespace=ingress.metadata.namespace, body=json.loads(json.dumps(annotation)), pretty=args.pretty)
                                except ApiException as e:
                                    print("Exception when calling AppsV1Api->patch_namespaced_ingress: %s\n" % e)
                                    print(payload.keys())
                                    print(type(payload))
                                    print(str(payload))

                            body = [
                                {"op": "replace", "path": "/spec/rules/" + str(rule_index) + "/http/paths/" + str(path_index) + "/backend/serviceName", "value": "rescaler"},
                                {"op": "replace", "path": "/spec/rules/" + str(rule_index) + "/http/paths/" + str(path_index) + "/backend/servicePort", "value": 3000}
                            ]
                            
                            try: 
                                logger.debug("Patch specifications: %s" %(json.loads(json.dumps(body))))

                                patch_ingress = ExtensionsV1beta1Api.patch_namespaced_ingress(name=ingress.metadata.name, namespace=ingress.metadata.namespace, body=json.loads(json.dumps(body)), pretty=args.pretty)
                                logger.info("Patched Ingress (ing) Name: %s" % (ingress.metadata.name))
                            except ApiException as e:
                                print("Exception when calling ExtensionsV1beta1Api->patch_namespaced_ingress: %s\n" % e)
                                print(payload.keys())
                                print(type(payload))
                                print(str(payload))
                            finally:
                                loop.run_until_complete(publish(json.loads(json.dumps(client.ApiClient().sanitize_for_serialization(ingress), indent=None)), loop))
                        path_index += 1
                    rule_index +=1
                 
                
    except ApiException as e:
        print("Exception when calling ExtensionsV1beta1Api->list_namespaced_ingress: %s\n" % e)
        print(payload.keys())
        print(type(payload))
        print(str(payload))

    logger.info("Output: %s" % (json.dumps(output)))
    return json.dumps(output)


async def publish(ingress_resource, loop):
    # client publish to NATS
    nc = NATS()
    
    msg = {"namespace": ingress_resource["metadata"]["namespace"], "name": ingress_resource["metadata"]["name"], "rules": ingress_resource["spec"]["rules"] }

    try:
        await nc.connect(servers=[args.nats_address], loop=loop,connect_timeout=args.conn_timeout, max_reconnect_attempts=args.conn_attempts, reconnect_time_wait=args.conn_wait)
    except ErrNoServers as e:
        # Could not connect to any server in the cluster.
        print(e)
        return

    async def message_handler(msg):
        subject = msg.subject
        reply = msg.reply
        data = msg.data.decode()
        print ("Received a message on '{subject} {reply}': {data}".format(
            subject=subject, reply=reply, data=data
        ))
            
    # Simple publisher and async subscriber via coroutine.
    sid = await nc.subscribe(args.topic, cb=message_handler)

    try:
        await nc.publish(args.topic, json.dumps(msg).encode('utf-8'))
        await nc.flush(0.500)

        output['data'].append(msg)
    except ErrConnectionClosed as e:
        print("Connection closed prematurely.")
    except ErrTimeout as e:
        print("Timeout occured when publishing msg i={}: {}".format(
            deploy, e))
    
    await nc.drain()

# Used only for local testing
if __name__ == '__main__':
    event = {"data": {"namespace": "sock-shop", "name": "front-end", "kind": "deployment", "replicas": 1, "labels": {"app": "front-end"}}}
    # event = {"data":'{"namespace": "demo", "name": "web", "kind": "statefulset", "replicas": 3, "labels": {"app": "nginx", "type": "statefulset"}}}
    context = {"context": {"function-name": "update-ingress", "timeout": "180", "runtime": "python3.6", "memory-limit": "128M"}}
    handle(event, context)
