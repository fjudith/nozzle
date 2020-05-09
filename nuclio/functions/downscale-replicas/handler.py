#!/usr/bin/env python

import argparse
import json
import logging
import os
from pprint import pprint

from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException

output = {"data":[]}

parser = argparse.ArgumentParser()
# Function related arguments
parser.add_argument('-md', '--max-deployment', help="Maximum number of Deployement replicas to last in the cluster", action="store_true", default=0)
parser.add_argument('-ms', '--max-statefulset', help="Maximum number of Statefulset replicas to last in the cluster", action="store_true", default=1)
# Kubernetes related arguments
parser.add_argument('--in-cluster', help="Use in cluster kubernetes config", action="store_true", default=True) #Remove ", default=True" if running locally
parser.add_argument('--pretty', help='Output pretty printed.', default=False)
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

def handle(event, context):
    payload = (event)['data']
    
    # Client to list namespaces
    CoreV1Api = client.CoreV1Api()
    
    # Client to list Deployments and StatefulSets
    AppsV1Api = client.AppsV1Api()

    if payload['kind'] == "deployment":
        deployment = AppsV1Api.read_namespaced_deployment(name=payload['name'], namespace=payload['namespace'], pretty=args.pretty)
        
        if not "kubectl.kubernetes.io/last-applied-configuration" in deployment.metadata.annotations:
            annotation = {
                "metadata": {
                    "annotations": {
                        "replicas.nozzle.io/last-known-configuration": str(payload['replicas'])
                    }
                }
            }

            logger.info("Backing up number of replicas of Deployment (deploy) Name: %s to %s" % (deployment.metadata.name, annotation))
            try:
                backup_replicas = AppsV1Api.patch_namespaced_deployment(name=payload['name'], namespace=payload['namespace'], body=annotation, pretty=args.pretty)
            except ApiException as e:
                print("Exception when calling AppsV1Api->patch_namespaced_deployment: %s\n" % e)
                print(payload.keys())
                print(type(payload))
                print(str(payload))
        
        body={'spec':{'replicas': args.max_deployment}}        
        try:
            api_response = AppsV1Api.patch_namespaced_deployment_scale(name=payload['name'], namespace=payload['namespace'], body=body, pretty=args.pretty)
            logger.info("Patched number of replicas of Deployment (deploy) Name: %s to %s" % (deployment.metadata.name, args.max_deployment))

            output['data'].append({'namespace': deployment.metadata.namespace, 'name': deployment.metadata.name, 'spec': body['spec'] })
        except ApiException as e:
            print("Exception when calling AppsV1Api->patch_namespaced_deployment_scale: %s\n" % e)
            print(payload.keys())
            print(type(payload))
            print(str(payload))
            
    elif payload['kind'] == "statefulset":
        statefulset = AppsV1Api.read_namespaced_stateful_set(name=payload['name'], namespace=payload['namespace'], pretty=args.pretty)
        
        if not "kubectl.kubernetes.io/last-applied-configuration" in statefulset.metadata.annotations:
            annotation = {
                "metadata":{
                    "annotations": {
                        "replicas.nozzle.io/last-known-configuration": str(payload['replicas'])
                    }
                }
            }

            logger.info("Backing up number of replicas of Statefulset (sts) Name: %s to %s" % (statefulset.metadata.name, annotation))
            try:
                backup_replicas = AppsV1Api.patch_namespaced_stateful_set(name=payload['name'], namespace=payload['namespace'], body=annotation, pretty=args.pretty)
            except ApiException as e:
                print("Exception when calling AppsV1Api->patch_namespaced_stateful_set: %s\n" % e)
                print(payload.keys())
                print(type(payload))
                print(str(payload))        
        
        body={'spec':{'replicas': args.max_statefulset}}
        try:
            api_response = AppsV1Api.patch_namespaced_stateful_set_scale(name=payload['name'], namespace=payload['namespace'], body=body, pretty=args.pretty)
            logger.info("Patched number of replicas of Statefulset (sts) Name: %s to %s" % (statefulset.metadata.name, args.max_statefulset))

            output['data'].append({'namespace': statefulset.metadata.namespace, 'name': statefulset.metadata.name, 'spec': body['spec'] })
        except ApiException as e:
            print("Exception when calling AppsV1Api->patch_namespaced_stateful_set_scale: %s\n" % e)
            print(payload.keys())
            print(type(payload))
            print(str(payload))
    else:
        msg = "SKIPPING: Resource is not of kind Deployment or Statefulset"
        print(msg)
        return(msg)

    logger.info("Output: %s" % (json.dumps(output)))
    return json.dumps(output)


# Used only for local testing
if __name__ == '__main__':
    event = {"data": {"namespace": "demo", "name": "web", "kind": "statefulset", "replicas": 3, "labels": {"app": "nginx", "type": "statefulset"}}}
    context = {"context": {"function-name": "downscale-replicas", "timeout": "180", "runtime": "python3.6", "memory-limit": "128M"}}
    handle(event, context)
