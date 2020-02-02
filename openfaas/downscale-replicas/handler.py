#!/usr/bin/env python

import asyncio
import argparse
import json
import logging
import os
from pprint import pprint

from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException

parser = argparse.ArgumentParser()
# Kubernetes related arguments
parser.add_argument('--in-cluster', help="use in cluster kubernetes config", action="store_true", default=True) #Remove ", default=True" if running locally
parser.add_argument('--pretty', help='Output pretty printed.', default=False)
# parser.add_argument('--dry-run', help='Indicates that modifications should not be persisted. Valid values are: - All: all dry run stages will be processed (optional)')

# NATS releated arguments
parser.add_argument('-a', '--nats-address', help="address of nats cluster", default=os.environ.get('NATS_ADDRESS', None))
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

def handle(req):
    payload = json.loads(req)
    
    # Client to list namespaces
    CoreV1Api = client.CoreV1Api()
    
    # Client to list Deployments and StatefulSets
    AppsV1Api = client.AppsV1Api()

    if payload['kind'] == "deployment":
        body={'spec':{'replicas': 0}}
        try:
            api_response = AppsV1Api.patch_namespaced_deployment_scale(name=payload['name'], namespace=payload['namespace'], body=body, pretty=args.pretty)
            pprint(api_response)
        except ApiException as e:
            print("Exception when calling AppsV1Api->patch_namespaced_deployment_scale: %s\n" % e)
            print(payload.keys())
            print(type(payload))
            print(str(payload))
            
    elif payload['kind'] == "statefulset":
        body={'spec':{'replicas': 1}}
        try:
            api_response = AppsV1Api.patch_namespaced_stateful_set_scale(name=payload['name'], namespace=payload['namespace'], body=body, pretty=args.pretty)
            pprint(api_response)
        except ApiException as e:
            print("Exception when calling AppsV1Api->patch_namespaced_stateful_set_scale: %s\n" % e)
            print(payload.keys())
            print(type(payload))
            print(str(payload))
    else:
        msg = "SKIPPING: Resource is not of kind Deployment or Statefulset"
        print(msg)
        return(msg)

# Used only for local testing
if __name__ == '__main__':
    req = '{"namespace": "demo", "name": "web", "kind": "statefulset", "replicas": 3, "labels": {"app": "nginx", "type": "statefulset"}}'
    handle(req)
