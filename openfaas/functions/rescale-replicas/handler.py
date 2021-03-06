import argparse
import json
import logging
import os
from pprint import pprint

from contextlib import contextmanager
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException

parser = argparse.ArgumentParser()
parser.add_argument('-r', '--rescaler', help="Name of the Rescaler deployment", default=os.environ.get('RESCALER_NAME', None))
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

def rescaleStatefulset(payload):
    # Client to manage Statefulset resources
    AppsV1Api = client.AppsV1Api()

    statefulsets = AppsV1Api.list_namespaced_stateful_set(namespace=payload['namespace'], pretty=args.pretty)

    for statefulset in statefulsets.items:

        if "replicas.nozzle.io/last-known-configuration" in statefulset.metadata.annotations:
            source_annotation = "replicas.nozzle.io/last-known-configuration"
            replicas = json.loads(statefulset.metadata.annotations[source_annotation])
        elif "kubectl.kubernetes.io/last-applied-configuration" in statefulset.metadata.annotations:
            source_annotation = "kubectl.kubernetes.io/last-applied-configuration"
            replicas = json.loads(statefulset.metadata.annotations[source_annotation])['spec']['replicas']
        else:
            next

        logger.info("Restoring replicas of Statefulset (sts) Name: %s to %s from Annotation: %s" % (statefulset.metadata.name, json.dumps(replicas), source_annotation))
        
        body={'spec':{'replicas': replicas}}
        
        try:
            logger.debug("Patch specifications: %s" %(json.loads(json.dumps(body))))
            api_response = AppsV1Api.patch_namespaced_stateful_set_scale(name=statefulset.metadata.name, namespace=payload['namespace'], body=body, pretty=args.pretty)

        except ApiException as e:
            print("Exception when calling AppsV1Api->patch_namespaced_stateful_set_scale: %s\n" % e)
            print(payload.keys())
            print(type(payload))
            print(str(payload))


def rescaleDeployment(payload):
    # Client to manage Deployment resources
    AppsV1Api = client.AppsV1Api()

    deployments = AppsV1Api.list_namespaced_deployment(namespace=payload['namespace'], pretty=args.pretty)

    for deployment in deployments.items:
        if not deployment.metadata.name == args.rescaler:
            if "replicas.nozzle.io/last-known-configuration" in deployment.metadata.annotations:
                source_annotation = "replicas.nozzle.io/last-known-configuration"
                replicas = json.loads(deployment.metadata.annotations[source_annotation])
            elif "kubectl.kubernetes.io/last-applied-configuration" in deployment.metadata.annotations:
                source_annotation = "kubectl.kubernetes.io/last-applied-configuration"
                replicas = json.loads(deployment.metadata.annotations[source_annotation])['spec']['replicas']
            else:
                next

            logger.info("Restoring replicas of Deployment (deploy) Name: %s to %s from Annotation: %s" % (deployment.metadata.name, json.dumps(replicas), source_annotation))
            
            body={'spec':{'replicas': replicas}}
            
            try:
                logger.debug("Patch specifications: %s" %(json.loads(json.dumps(body))))
                api_response = AppsV1Api.patch_namespaced_deployment_scale(name=deployment.metadata.name, namespace=payload['namespace'], body=body, pretty=args.pretty)

            except ApiException as e:
                print("Exception when calling AppsV1Api->patch_namespaced_deployment_scale: %s\n" % e)
                print(payload.keys())
                print(type(payload))
                print(str(payload))

def restoreIngress(payload):
    # Client to manage Ingress resources
    ExtensionsV1beta1Api = client.ExtensionsV1beta1Api()

    ingresses = ExtensionsV1beta1Api.list_namespaced_ingress(namespace=payload['namespace'], pretty=args.pretty)
    
    for ingress in ingresses.items:

        if "rules.nozzle.io/last-known-configuration" in ingress.metadata.annotations:
            source_annotation = "rules.nozzle.io/last-known-configuration"
            last_config = json.loads(ingress.metadata.annotations[source_annotation])
        elif "kubectl.kubernetes.io/last-applied-configuration" in ingress.metadata.annotations:
            source_annotation = "kubectl.kubernetes.io/last-applied-configuration"
            last_config = json.loads(ingress.metadata.annotations[source_annotation])['spec']['rules']
        else:
            next

        logger.info("Restoring rules of Ingress (ing) Name: %s from Annotation: %s" % (ingress.metadata.name, source_annotation))

        body = [
                {"op": "replace", "path": "/spec/rules" , "value": last_config}
            ]

        try:
            logger.debug("Patch specifications: %s" %(json.loads(json.dumps(body))))
            patch_ingress = ExtensionsV1beta1Api.patch_namespaced_ingress(name=ingress.metadata.name, namespace=ingress.metadata.namespace, body=json.loads(json.dumps(body)), pretty=args.pretty)
        
        except ApiException as e:
            print("Exception when calling ExtensionsV1beta1Api->patch_namespaced_ingress: %s\n" % e)
            print(payload.keys())
            print(type(payload))
            print(str(payload))

def removeRescaler(payload):
    # Client to remove Deployment resources
    AppsV1Api = client.AppsV1Api()

    # Client to remove ConfigMap and Service resources
    CoreV1Api = client.CoreV1Api()

    try:
        logger.info("Remove rescaler Deployment from Namespace: %s" % payload['namespace'])
        patch_ingress = AppsV1Api.delete_namespaced_deployment(name=args.rescaler, namespace=payload['namespace'], pretty=args.pretty)
        
    except ApiException as e:
        print("Exception when calling AppsV1Api.delete_namespaced_deployment: %s\n" % e)
        print(payload.keys())
        print(type(payload))
        print(str(payload))

    try:
        logger.info("Remove rescaler Service from Namespace: %s" % payload['namespace'])
        patch_ingress = CoreV1Api.delete_namespaced_service(name=args.rescaler, namespace=payload['namespace'], pretty=args.pretty)
        
    except ApiException as e:
        print("Exception when calling CoreV1Api.delete_namespaced_service: %s\n" % e)
        print(payload.keys())
        print(type(payload))
        print(str(payload))
    
    try:
        logger.info("Remove rescaler ConfigMap from Namespace: %s" % payload['namespace'])
        patch_ingress = CoreV1Api.delete_namespaced_config_map(name=args.rescaler, namespace=payload['namespace'], pretty=args.pretty)
        
    except ApiException as e:
        print("Exception when calling CoreV1Api.delete_namespaced_config_map: %s\n" % e)
        print(payload.keys())
        print(type(payload))
        print(str(payload))

def handle(req):
    payload = json.loads(req)

    rescaleStatefulset(payload)
    rescaleDeployment(payload)
    restoreIngress(payload)
    removeRescaler(payload)

# Used only for local testing
if __name__ == '__main__':
    req = '{"namespace": "sock-shop", "ingress": "front-end"}'
    handle(req)

