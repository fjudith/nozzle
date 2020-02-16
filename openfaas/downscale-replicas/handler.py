#!/usr/bin/env python

import argparse
import json
import logging
import os
from pprint import pprint

from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException

parser = argparse.ArgumentParser()
# Kubernetes related arguments
parser.add_argument('--in-cluster', help="Use in cluster kubernetes config", action="store_true", default=True) #Remove ", default=True" if running locally
parser.add_argument('--pretty', help='Output pretty printed.', default=False)
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
