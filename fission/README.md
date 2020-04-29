
# Nozzle

This document demonstrates how to deploy Nozzle in a Kubernetes cluster running the Fission serverless platform.

Serverless is a particular kind of microservices architecture that splits services into ephemeral functions to enhance observability and cost efficiency.
Serverless platforms are orchestration tools to efficiently run the code when it is required. To acheive this they support a set of trigger to react on events like HTTP requests, scheduled jobs, message queue publishing, etc.

> **Warning**: The functions code has been ported from Openfaas and modified for Fission for the NATS Streaming instance.

## Pre-requesits

Fission requires you to install the [Fission client](https://github.com/fission/fission/releases) in order to deploy the various objects (functions, triggers, routes, etc.)
You will also need to get a copy of this repository to run the commands:

```bash
git clone https://github.com/fjudith/nozzle

cd nozzle/fission
```

## Manifests

The [manifests](./manifests/) directory contains the required [RBAC and ServiceAccounts](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) enabling each function to interact with the Kubernetes API.
It also contain an application running 3 replicas of the [nginx-alpine](https://hub.docker.com/r/amd64/nginx) image in the form of Deployment and Statefulset to demonstrate du Nozzle concept.

```bash
kubectl apply -f manifests/
```

## Create an environment

Create the Python3 environment for Nozzle functions.

```bash
fission env create \
  --name nozzle \
  --image fission/python-env:latest \
  --builder fission/python-builder:latest \
  --spec --version 3

fission env list
```

## Functions

### Publish-Resources

The `publish-resources` function aims to collect the number of replicas of both deployment and statefulset resources from namespaces configured with the label `nozzle=true`.
Each selected resource is then published as an individual JSON in a [NATS Streaming](https://docs.nats.io/nats-streaming-concepts/intro) message queue for further processing by other functions synchronously.

```bash
fission function create \
  --env "nozzle" \
  --name "publish-resources" \
  --src "functions/publish-resources/*" \
  --entrypoint "handler.handle" \
  --spec
```

### Downscale-Replicas

The `downscale-replicas` function receives messages pushed by the `publish-resources` function to perform the backup and scale down of the resource specified in each message.
The function is triggered by Kubeless using the publish-subribe mechanism leveraging the [NATS Streamin trigger](https://docs.fission.io/docs/triggers/message-queue-trigger/nats-streaming/).

> **Note**: Fission pre-serialize message in JSON format to functions

```bash
fission function create \
  --env "nozzle" \
  --name "downscale-replicas" \
  --src "functions/downscale-replicas/*" \
  --entrypoint "handler.handle" \
  --spec
```

Execute the following command to create a `trigger` that run the `downscale-resources` function on NATS Streaming publish events.

```bash
fission mqtrigger create --name downscale-replicas --function downscale-replicas --mqtype='nats-streaming' --topic 'k8s_replicas' --spec
```

### Update-Ingress

The `update-ingress` function receives messages pushed by the `publish-resources` function to perform the backup and modification of the ingress rules associated to deployment or statefulset resources.
The function is triggered by Kubeless using the publish-subsribe mechanism leveraging the [NATS Streamin trigger](https://docs.fission.io/docs/triggers/message-queue-trigger/nats-streaming/).

```bash
fission function create \
  --env "nozzle" \
  --name "update-ingress" \
  --src "functions/update-ingress/*" \
  --entrypoint "handler.handle" \
  --spec
```

Execute the following command to create a `trigger` that run the `downscale-resources` function on NATS Streaming publish events.

```bash
fission mqtrigger create --name update-ingress --function update-ingress --mqtype='nats-streaming' --topic 'k8s_replicas' --spec
```

### Deploy-Rescaler

The `deploy-rescaler` function receives messages pushed by the `publish-resources` function to inject the `rescaler` website inside the namespace associeted with either deployment and statefulset resources.
The function is triggered by Kubeless using the publish-subscribe mechanism leveraging the [NATS Streamin trigger](https://docs.fission.io/docs/triggers/message-queue-trigger/nats-streaming/).

```bash
fission function create \
  --env "nozzle" \
  --name "deploy-rescaler" \
  --src "functions/deploy-rescaler/*" \
  --entrypoint "handler.handle" \
  --spec
```

Execute the following command to create a `trigger` that run the `downscale-resources` function on NATS Streaming publish events.

```bash
fission mqtrigger create --name deploy-rescaler --function deploy-rescaler --mqtype='nats-streaming' --topic 'k8s_ingresses' --spec
```

---

## Teardown

```bash
fission function delete --name publish-resources

```

## Test environment

Scripts are validated on the using the following environment.

* [Kubernetes](https://github.com/kubernetes/kubernetes): `v1.16.3`
* [Nats operator](https://github.com/nats-io/nats-operator): `v0.6.0`
* [Nats cluster](https://github.com/nats-io/nats-server): `v2.1.2`
* [Nats Streaming operator](https://github.com/nats-io/nats-streaming-operator): `v0.3.0`
* [Nats Streaming cluster](https://github.com/nats-io/nats-server): `v0.17.0`
* [Kubefwd](https://github.com/txn2/kubefwd): `1.11.1`

## Reference

* [Packaging source code](https://docs.fission.io/docs/usage/package)
* [How to develop a serverless application with Fission (part 1)](https://tachingchen.com/blog/how-to-develop-a-serverless-application-with-fission-pt-1/)
* [How to develop a serverless application with Fission (part 2)](https://tachingchen.com/blog/how-to-develop-a-serverless-application-with-fission-pt-2/)