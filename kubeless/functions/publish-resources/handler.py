#!/usr/bin/env python

import asyncio
import argparse
import json
import logging
import os

from kubernetes import client, config, watch

from nats.aio.client import Client as NATS
from nats.aio.errors import ErrConnectionClosed, ErrTimeout, ErrNoServers

parser = argparse.ArgumentParser()
# Function related arguments
parser.add_argument('-t', '--topic', help="NATS Streaming topic", default="k8s.replicas")
parser.add_argument('-x', '--exclude', help="Name of the Rescaler deployment", default=os.environ.get('RESCALER_NAME', None))
# Kubernetes related arguments
parser.add_argument('-l', '--selector', help="Selector (label query) to filter on, supports '=', '==', and '!='.(e.g. -l key1=value1,key2=value2)", default='nozzle=true')
parser.add_argument('--in-cluster', help="Use in cluster kubernetes config", action="store_true", default=True) #Remove ", default=True" if running locally
# NATS related arguments
parser.add_argument('-a', '--nats-address', help="Address of nats cluster", default=os.environ.get('NATS_ADDRESS', None))
parser.add_argument('--connect-timeout', help="NATS connect timeout (s)", type=int, default=10, dest='conn_timeout')
parser.add_argument('--max-reconnect-attempts', help="Number of times to attempt reconnect", type=int, default=5, dest='conn_attempts')
parser.add_argument('--reconnect-time-wait', help="How long to wait between reconnect attempts", type=int, default=1, dest='conn_wait')
# Logger arguments
parser.add_argument('-d', '--debug', help="Enable debug logging", action="store_true")
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

if not args.nats_address:
    logger.critical("No NATS cluster specified")
    exit(parser.print_usage())
else:
    logger.debug("Using nats address: %s", args.nats_address)

if args.in_cluster:
    config.load_incluster_config()
else:
    try:
        config.load_kube_config()
    except Exception as e:
        logger.critical("Error creating Kubernetes configuration: %s", e)
        exit(2)

async def publish(loop):

    # Client to list namespaces
    CoreV1Api = client.CoreV1Api()

    # Client to list Deployments and StatefulSets
    AppsV1Api = client.AppsV1Api()

    # client publish to NATS
    nc = NATS()
    
    try:
        await nc.connect(servers=[args.nats_address], loop=loop, connect_timeout=args.conn_timeout, max_reconnect_attempts=args.conn_attempts, reconnect_time_wait=args.conn_wait)
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

    async def get_deployments():
        for ns in CoreV1Api.list_namespace(label_selector=args.selector).items:
            for deploy in AppsV1Api.list_namespaced_deployment(ns.metadata.name).items:
                logger.info("Namespace: %s Deployment: %s Replica: %s" % (deploy.metadata.namespace, deploy.metadata.name, deploy.spec.replicas))
                msg = {'namespace': deploy.metadata.namespace, 'name': deploy.metadata.name, 'kind': 'deployment', 'replicas': deploy.spec.replicas, 'labels': deploy.spec.template.metadata.labels}
                
                logger.debug("Publishing Deployment: %s" % (json.dumps(msg)))
                
                if deploy.spec.replicas > 0 and not deploy.metadata.name == args.exclude:
                    try:
                        await nc.publish(args.topic, json.dumps(msg).encode('utf-8'))
                        await nc.flush(0.500)
                    except ErrConnectionClosed as e:
                        print("Connection closed prematurely.")
                        break
                    except ErrTimeout as e:
                        print("Timeout occured when publishing msg i={}: {}".format(
                            deploy, e))
    
    async def get_statefulsets():
        for ns in CoreV1Api.list_namespace(label_selector=args.selector).items:
            for sts in AppsV1Api.list_namespaced_stateful_set(ns.metadata.name).items:
                logger.info("Namespace: %s StatefulSet: %s Replica: %s" % (sts.metadata.namespace, sts.metadata.name, sts.spec.replicas))
                msg = {'namespace': sts.metadata.namespace, 'name': sts.metadata.name, 'kind': 'statefulset', 'replicas': sts.spec.replicas, 'labels': sts.spec.template.metadata.labels}

                logger.debug("Publishing Statefulset: %s" % (json.dumps(msg)))
                
                if sts.spec.replicas > 1:
                    try:
                        await nc.publish(args.topic, json.dumps(msg).encode('utf-8'))
                        await nc.flush(0.500)
                    except ErrConnectionClosed as e:
                        print("Connection closed prematurely.")
                        break
                    except ErrTimeout as e:
                        print("Timeout occured when publishing msg i={}: {}".format(
                            sts, e))
    
    await asyncio.gather(
        get_deployments(),
        get_statefulsets()
    )
    await nc.drain()



def handle(event, context):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(publish(loop))
    except KeyboardInterrupt:
        logger.info('keyboard shutdown')
    finally:
        logger.info('closing event loop')
        loop.close()

# Used only for local testing
if __name__ == '__main__':
    event = {}
    context = {}
    handle(event, context)