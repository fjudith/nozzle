# Nozzle

This document demonstrates how to deploy Nozzle in a Kubernetes cluster running the Nuclio serverless platform.

Serverless is a particular kind of microservices architecture that splits services into ephemeral functions to enhance observability and cost efficiency.
Serverless platforms are orchestration tools to efficiently run the code when it is required. To acheive this they support a set of trigger to react on events like HTTP requests, scheduled jobs, message queue publishing, etc.

## Pre-requesits

Nuclio requires you to install the [Nuclio client](https://github.com/nuclio/nuclio/releases) in order to deploy the various objects (functions, triggers, etc.)
You will also need to get a copy of this repository to run the commands:

```bash
git clone https://github.com/fjudith/nozzle

cd nozzle/nuclio
```

## Manifests

The [manifests](./manifests/) directory contains the required [RBAC and ServiceAccounts](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) enabling each function to interact with the Kubernetes API.
It also contain an application running 3 replicas of the [nginx-alpine](https://hub.docker.com/r/amd64/nginx) image in the form of Deployment and Statefulset to demonstrate Nozzle concepts.

```bash
kubectl apply -f manifests/
```

## Functions

### Publish-Resources

The `publish-resources` function aims to collect the number of replicas of both deployment and statefulset resources from namespaces configured with the label `nozzle=true`.
Each selected resource is then published as an individual JSON in a [NATS](https://nats.io) message queue for further processing by other functions synchronously.

```bash
nuctl deploy publish-resources --namespace nuclio \
  --path functions/publish-resources/
```

### Downscale-Replicas

The `downscale-replicas` function receives messages pushed by the `publish-resources` function to perform the backup and scale down of the resource specified in each message.
The function is triggered by Nuclio using the publish-subribe mechanism leveraging the [NATS trigger](https://nuclio.io/docs/latest/reference/triggers/nats/).

> **Nuclio**: Kubeless pre-serialize message in JSON format for functions

```bash
nuctl deploy downscale-replicas --namespace nuclio \
  --path functions/downscale-replicas/
```

### Update-Ingress

The `update-ingress` function receives messages pushed by the `publish-resources` function to perform the backup and modification of the ingress rules associated to deployment or statefulset resources.
The function is triggered by Nuclio using the publish-subsribe mechanism leveraging the [NATS trigger](https://nuclio.io/docs/latest/reference/triggers/nats/).

```bash
nuctl deploy update-ingress --namespace nuclio \
  --path functions/update-ingress/
```

### Deploy-Rescaler

The `deploy-rescaler` function receives messages pushed by the `publish-resources` function to inject the `rescaler` website inside the namespace associeted with either deployment and statefulset resources.
The function is triggered by Nuclio using the publish-subscribe mechanism leveraging the [NATS trigger](https://nuclio.io/docs/latest/reference/triggers/nats/).

```bash
nuctl deploy deploy-rescaler --namespace nuclio \
  --path functions/deploy-rescaler/
```

## Rescale-Replicas

The `rescale-replicas` function receives message posted by the `rescaler` website pod to restore amount of replicas that were reduced by the `downscale-replicas` function. It also restore the ingress rules modified by the `update-ingress` function.
The function is triggered by Nuclio using the remote procedure call mechanism leveraging the [HTTP Trigger](https://kubeless.io/docs/http-triggers/)

```bash
nuctl deploy rescale-replicas --namespace nuclio \
  --path functions/rescale-replicas/
```

## Test environment

Scripts are validated on the using the following environment.

* [Kubernetes](https://github.com/kubernetes/kubernetes): `v1.16.3`
* [Nats operator](https://github.com/nats-io/nats-operator): `v0.6.0`
* [Nats cluster](https://github.com/nats-io/nats-server): `v2.1.2`
* [Kubefwd](https://github.com/txn2/kubefwd): `1.11.1`

## References

* **Kubernetes CoreV1Api** : <https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/CoreV1Api.md#list_namespace>
* **Kubernetes AppsV1Api** : <https://github.com/kubernetes-client/python/blob/master/kubernetes/docs/AppsV1Api.md#list_namespaced_deployment>
* **Crontab Generator**: <https://crontab-generator.org>
* **Python running task concurently**: <https://docs.python.org/3/library/asyncio-task.html#running-tasks-concurrently>
* **Resolve ArgumentParser conflict**: <https://stackoverflow.com/questions/12818146/python-argparse-ignore-unrecognised-arguments>
