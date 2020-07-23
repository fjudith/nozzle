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

output = {"data":[]}

parser = argparse.ArgumentParser()
# Function related arguments
parser.add_argument('-f', '--filename', help="JSON file that contains list of deployments and statefulsets to downscale")
parser.add_argument('-o', '--output', help="JSON output file that contains list of ingress resources", default=os.environ.get('JSON_OUTPUT', default="/tmp/update-ingress.json"))
# Kubernetes related arguments
parser.add_argument('--in-cluster', help="Use in cluster kubernetes config", action="store_true", default=True) # "default=False" if running locally
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

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def update(payload):
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

async def publish(ingress_resource, loop):
    msg = {"namespace": ingress_resource["metadata"]["namespace"], "name": ingress_resource["metadata"]["name"], "rules": ingress_resource["spec"]["rules"] }
    output['data'].append(msg)

def handle(event, context):
    with open(args.filename, 'r') as intpufile:
        JSON = json.load(intpufile)
    
    for payload in JSON['data']:
        update(payload)

    logger.info("Output: %s" % (json.dumps(output)))

    with open(args.output, 'w') as outfile:
        logger.info("Write JSON: %s" % (args.output))
        json.dump(output, outfile)

# Used only for local testing
if __name__ == '__main__':
    event = {}
    context = {}
    handle(event, context)
