#!/usr/bin/env python

from __future__ import print_function
import time
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException

import argparse
import json
import logging
import os
from pprint import pprint

# Command Arguments
parser = argparse.ArgumentParser()
parser.add_argument('--in-cluster', help="Use in cluster kubernetes config", action="store_true")
parser.add_argument('-l', '--selector', help="Selector (label query) to filter on, supports '=', '==', and '!='.(e.g. -l key1=value1,key2=value2)", default='nozzle=true')
parser.add_argument('-d', '--debug', help="enable debug logging", action="store_true")
parser.add_argument('-t', '--timeout', help="timout seconds", default='30')
parser.add_argument('-p', '--pretty', help="pretty printed output", action="store_true")
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

# Client to list namespaces
CoreV1Api = client.CoreV1Api()

# Client to list Deployments and StatefulSets
AppsV1Api = client.AppsV1Api()

try:
    w = watch.Watch()
    
    for ns in CoreV1Api.list_namespace(label_selector=args.selector).items:
        logger.info("Namespace: %s Labels: %s" % (ns.metadata.name, ns.metadata.labels))
        for deploy in AppsV1Api.list_namespaced_deployment(ns.metadata.name).items:
            logger.info("Namespace: %s Deployment: %s Replica: %s" % (deploy.metadata.namespace, deploy.metadata.name, deploy.spec.replicas))
        for sts in AppsV1Api.list_namespaced_stateful_set(ns.metadata.name).items:
            logger.info("Namespace: %s StatefulSet: %s Replica: %s" % (sts.metadata.namespace, sts.metadata.name, sts.spec.replicas))


except ApiException as e:
    print("Exception when calling AppsV1Api->list_namespace: %s\n" % e)
