#!/usr/bin/env python

import sys
import os
import imp
import argparse
import json
import yaml
import logging
from pprint import pprint

from contextlib import contextmanager
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException

# from bottle import route, run, template, request

parser = argparse.ArgumentParser()
# Kubernetes related arguments
parser.add_argument('--in-cluster', help="use in cluster kubernetes config", action="store_true", default=True) # "default=False" if running locally
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

@contextmanager
def _pass_conflicts():
    try:
        yield
    except ApiException as e:
        body = json.loads(e.body)
        if body['reason'] == 'AlreadyExists':
            logger.info("{} already exists, skipping!".format(body['details']))
            pass
        else:
            raise e


def service(req):
    # Client to list Services
    CoreV1Api = client.CoreV1Api()
    namespace = req['namespace']

    manifest = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "labels": {
                "app": "rescaler",
                "tier": "web"
            },
            "name": "rescaler",
            "namespace": namespace
        },
        "spec": {
            "clusterIP": "None",
            "ports": [
                {
                    "name": "web",
                    "port": 3000,
                    "protocol": "TCP",
                    "targetPort": 80
                }
            ],
            "selector": {
                "app": "rescaler",
                "tier": "web"
            },
            "sessionAffinity": "None",
            "type": "ClusterIP"
        },
    }

    with _pass_conflicts():
        api_response = CoreV1Api.create_namespaced_service(namespace=namespace, body=manifest, pretty=args.pretty)
        logger.info("Created Service name: %s Namespace: %s" % (api_response.metadata.name, api_response.metadata.namespace))


def deployment(req):
    # Client to Manage Web-Rescale deployment
    AppsV1Api = client.AppsV1Api()
    
    namespace = req['namespace']
    
    # Instantiate the Deployment object
    manifest = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "annotations": {"app": "rescaler"},
            "deletionGracePeriodSeconds": 30,
            "labels": {"app": "rescaler", "tier": "web"},
            "name": "rescaler",
            "namespace": namespace
        },
        "spec": {
            "progressDeadlineSeconds": 600,
            "replicas": 1,
            "revision_history_limit": 10,
            "selector": {
                "matchLabels": {"app": "rescaler", "tier": "web"}
            },
            "strategy": {
                "rollingUpdate": {
                    "maxSurge": "25%",
                    "maxUnavailable": "25%"
                },
                "type": "RollingUpdate"
            },
            "template": {
                "metadata": {
                    "labels": {"app": "rescaler", "tier": "web"}
                },
                "spec": {
                    "containers": [
                        {
                            "image": "docker.io/amd64/nginx:1.16-alpine",
                            "imagePullPolicy": "Always",
                            "name": "nginx",
                            "ports": [
                                {
                                    "containerPort": 80,
                                    "name": "web",
                                    "protocol": "TCP"
                                }
                            ],
                            "resources": {},
                            "volumeMounts": [
                                {
                                    "name": "www",
                                    "mountPath": "/usr/share/nginx/html/index.html",
                                    "subPath": "index.html"
                                },
                                {
                                    "name": "default",
                                    "mountPath": "/etc/nginx/conf.d/default.conf",
                                    "subPath": "default.conf"
                                }
                            ],
                            "terminationMessagePath": "/dev/termination-log",
                            "terminationMessagePolicy": "File"
                        }
                    ],
                    "volumes": [
                        {
                        "name": "www",
                        "configMap": {"name": "rescaler", "items": [{"key": "index.html", "path": "index.html"}]}
                        },
                        {
                        "name": "default",
                        "configMap": {"name": "rescaler", "items": [{"key": "default.conf", "path": "default.conf"}]}
                        }
                    ],
                    "dnsPolicy": "ClusterFirst",
                    "restartPolicy": "Always",
                    "schedulerName": "default-scheduler",
                    "securityContext": {},
                    "terminationGracePeriodSeconds": 10
                }
            }
        }
    }

    with _pass_conflicts():
        api_response = AppsV1Api.create_namespaced_deployment(namespace=namespace, body=manifest, pretty=args.pretty)
        logger.info("Created Deployment name: %s Namespace: %s" % (api_response.metadata.name, api_response.metadata.namespace))


def configmap(req):
    # Client to list Services
    CoreV1Api = client.CoreV1Api()
    
    namespace = req['namespace']
    name      = req['name']
    host      = req['rules'][0]['host']
    
    index_html = ''.join(('<!DOCTYPE html>',
        '<html lang="fr">\n',
        '<head>\n',
        '<meta http-equiv="X-UA-Compatible" content="IE=Edge, chrome=1" />\n',
        f'<head><title>rescaler: {host}</title></head>\n',
        '<body>\n',
        f'<h1>{host}</h1>\n',
        '<form id="rescaler" >\n',
        '<label for="namespace">Namespace</label>\n',
        f'<input id="namespace" name="namespace" value="{namespace}">\n',
        '<label for="name">Ingress name</label>\n',
        f'<input id="name" name="ingress" value="{name}">\n',
        '</p>\n',
        'Click the <b>Rescale</b> button to restore <code>Deployment</code> and/or <code>Statefulset</code> replicas</p>\n',
        '<input type="submit" value="Rescale" />\n',
        '</form>\n',
        '</body>\n',
        '<script>\n',
        '"use strict";\n',
        'window.addEventListener( "load", function () {\n',
        'function sendData() {\n',
        '    var path  = "/function/rescale-replicas.openfaas-fn"\n',
        '\n',
        '    const XHR = new XMLHttpRequest();\n',
        '\n',
        '    // Bind the FormData object and the form element\n',
        '    const FD = new FormData( form );\n',
        '\n',
        '    // Define what happens on successful data submission\n',
        '    XHR.addEventListener( "load", function(event) {\n',
        '    alert( event.target.responseText );\n',
        '    } );\n',
        '\n',
        '    // Define what happens in case of error\n',
        '    XHR.addEventListener( "error", function( event ) {\n',
        '    alert( "Oops! Something went wrong." );\n',
        '    } );\n',
        '\n',
        '    // Set up our request\n',
        '    XHR.open( "POST", path );\n',
        '\n',
        '    XHR.setRequestHeader("Content-Type", "application/json;charset=UTF-8");\n',
        '    var json = {};\n',
        '    for (const [key, value]  of FD.entries()) {\n',
        '           json[key] = value;\n',
        '    }\n',
        '    var json = JSON.stringify(json);\n',
        '    console.info(json);\n',
        '\n',
        '    // The data sent is what the user provided in the form\n',
        '    XHR.send( json );\n',
        '}\n',
        '\n',
        '// Access the form element...\n',
        'var form = document.getElementById( "rescaler" );\n',
        '\n',
        '// ...and take over its submit event.\n',
        'form.addEventListener( "submit", function ( event ) {\n',
        '    event.preventDefault();\n',
        '\n',
        '    sendData();\n',
        '} );\n',
        '} );\n',
        '</script>\n',
        '</html>'
    ))

    default_config = ''.join(('',
        '\n',
        'server {\n',
        '   charset UTF-8;\n',
        '   listen 80;\n',
        '   server_name  localhost;\n',
        '   resolver kube-dns.kube-system valid=10s;\n',
        '\n',
        '   location / {\n',
        '       root /usr/share/nginx/html;\n',
        '       index  index.html index.htm;\n',
        '   }\n',
        '   location /function/ {\n',
        '       proxy_set_header        X-Real-IP $remote_addr;\n',
        '       proxy_set_header        X-Forwarded-For $proxy_add_x_forwarded_for;\n',
        '       proxy_set_header        X-NginX-Proxy true;\n',
        '       proxy_pass              http://gateway.openfaas.svc.cluster.local:8080;\n',
        '       proxy_http_version 1.1;\n',
        '       proxy_ssl_session_reuse off;\n',
        '       proxy_set_header        Host $http_host;\n',
        '       proxy_redirect          off;\n',
        '\n',
        '       add_header    "Access-Control-Allow-Origin" "*" always;\n',
        '       add_header    "Access-Control-Allow-Methods" "GET, POST, OPTIONS" always;\n',
        '       add_header    "Access-Control-Allow-Headers" "Origin, X-Requested-With, Content-Type, Accept" always;\n',
        '       add_header    "Access-Control-Allow-Credentials" "true" always;\n',
        '   }\n',
        '\n',
        '   location ~ /\. {\n',
        '       deny all;\n',
        '   }\n',
        '}\n'
    ))

    # Instantiate the ConfigMap object
    manifest = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "annotations": {"app": "rescaler"},
            "deletion_grace_period_seconds": 30,
            "labels": {"app": "rescaler"},
            "name": "rescaler",
            "namespace": namespace
        },
        "data": {"index.html": index_html, "default.conf": default_config},
    }


    with _pass_conflicts():
        api_response = CoreV1Api.create_namespaced_config_map(namespace=namespace, body=manifest, pretty=args.pretty)
        logger.info("Created Configmap name: %s Namespace: %s" % (api_response.metadata.name, api_response.metadata.namespace))     


def handle(req):
    payload = json.loads(req)
    configmap(payload)
    service(payload)
    deployment(payload)

if __name__ == '__main__':
    req = '{"namespace": "sock-shop", "name": "frontend", "rules": [{"host": "shop.weavelab.io", "http": {"paths": [{"backend": {"serviceName": "frontend", "servicePort": 80}, "path": "/"}]}}]}'
    handle(req)