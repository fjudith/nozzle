# Nozzle

This document show you how to deploy Nozzle in a Kubernetes cluster running the Kubeless serverless platform.

Serverless is a particular kind of microservices architecture that splits services into ephemeral functions to enhance observability and cost efficiency.
Serverless platforms are orchestration tools to efficiently run the code when it is required. To acheive this they support a set of trigger to react on events like HTTP requests, scheduled jobs, message queue publishing, etc.

## Pre-requesits

Kubeless requires you to install the [Kubeless client](https://github.com/kubeless/kubeless/releases) in order to deploy the various objects (functions, triggers, etc.)
You will also need to get a copy of this repository to run the commands:

```bash
git clone https://github.com/fjudith/nozzle

cd nozzle/kubeless
```

## Manifests

The [manifests](./manifests/) directory contains the required [RBAC and ServiceAccounts](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) enabling each function to interact with the Kubernetes API.
It also contain an application running 3 replicas of the [nginx-alpine](https://hub.docker.com/r/amd64/nginx) image in the form of Deployment and Statefulset to demonstrate du Nozzle concept.

```bash
kubectl apply -f manifests/
```

## Functions

### Publish-Resources

The `publish-resources` function aims to collect the number of replicas of both deployment and statefulset resources from namespaces configured with the label `nozzle=true`.
Each selected resource is then published as an individual JSON in a [NATS](https://nats.io) message queue for further processing by other functions synchronously.

```bash
kubeless function deploy publish-resources \
  --namespace kubeless \
  --runtime python3.6 \
  --handler handler.handle \
  --from-file functions/publish-resources/handler.py \
  --dependencies functions/publish-resources/requirements.txt \
  --env NATS_ADDRESS='nats://nats-cluster.nats-io:4222' \
  --env RESCALER_NAME='rescaler' && \
kubectl -n kubeless patch deployment publish-resources -p '{"spec":{"template":{"spec":{"serviceAccountName":"kubeless-replica-view"}}}}'
```

Execute the following command to create a `trigger` that run the `function` every 5 minutes.

```bash
kubeless trigger cronjob create publish-resources --namespace kubeless --function publish-resources --schedule '*/5 * * * *'
```

### Downscale-Replicas

The `downscale-replicas` function receives messages pushed by the `publish-resources` function to perform the backup and scale down of the resource specified in each message.
The function is triggered by Kubeless using the publish-subribe mechanism leveraging the [NATS trigger](https://kubeless.io/docs/pubsub-functions/).

> **Note**: Kubeless pre-serialize message in JSON format for functions

```bash
kubeless function deploy downscale-replicas \
  --namespace kubeless \
  --runtime python3.6 \
  --handler handler.handle \
  --from-file functions/downscale-replicas/handler.py \
  --dependencies functions/downscale-replicas/requirements.txt \
  --env NATS_ADDRESS='nats://nats-cluster.nats-io:4222' && \
kubectl -n kubeless patch deployment downscale-replicas -p '{"spec":{"template":{"spec":{"serviceAccountName":"kubeless-replica-manage"}}}}'
```

Execute the following command to create a `trigger` that run the `downscale-resources` function on NATS push events.

```bash
kubeless trigger nats create downscale-replicas --namespace kubeless --function-selector created-by=kubeless,function=downscale-replicas --trigger-topic 'k8s_replicas'
```

### Update-Ingress

The `update-ingress` function receives messages pushed by the `publish-resources` function to perform the backup and modification of the ingress rules associated to deployment or statefulset resources.
The function is triggered by Kubeless using the publish-subsribe mechanism leveraging the [NATS trigger](https://kubeless.io/docs/pubsub-functions/).

```bash
kubeless function deploy update-ingress \
  --namespace kubeless \
  --runtime python3.6 \
  --handler handler.handle \
  --from-file functions/update-ingress/handler.py \
  --dependencies functions/update-ingress/requirements.txt \
  --env NATS_ADDRESS='nats://nats-cluster.nats-io:4222' && \
kubectl -n kubeless patch deployment update-ingress -p '{"spec":{"template":{"spec":{"serviceAccountName":"kubeless-ingress-manage"}}}}'
```

Execute the following command to create a `trigger` that run the `downscale-resources` function on NATS push events.

```bash
kubeless trigger nats create update-ingress --namespace kubeless --function-selector created-by=kubeless,function=update-ingress --trigger-topic 'k8s_replicas'
```

### Deploy-Rescaler

The `deploy-rescaler` function receives messages pushed by the `publish-resources` function to inject the `rescaler` website inside the namespace associeted with either deployment and statefulset resources.
The function is triggered by Kubeless using the publish-subscribe mechanism leveraging the [NATS trigger](https://kubeless.io/docs/pubsub-functions/).

```bash
kubeless function deploy deploy-rescaler \
  --namespace kubeless \
  --runtime python3.6 \
  --runtime-image docker.io/fjudith/deploy-rescaler:kubeless-python3.6 \
  --handler handler.handle \
  --env TRIGGER_URL='http://rescale-replicas.kubeless.svc.cluster.local:8080' && \
kubectl -n kubeless patch deployment deploy-rescaler -p '{"spec":{"template":{"spec":{"serviceAccountName":"kubeless-deployment-manage"}}}}'
```

Execute the following command to create a `trigger` that run the `deploy-rescaler` function on NATS push events.

```bash
kubeless trigger nats create deploy-rescaler --namespace kubeless --function-selector created-by=kubeless,function=deploy-rescaler --trigger-topic 'k8s_ingresses'
```

#### Limitation

Kubeless does not support adding files outside of the `handler` and `dependencies` files.
But it provides a mechanism allowing to specify a custom pre-built image containing all required files to run the function (i.e handler, dependencies, static content, etc.) using the `--runtime-image` command line argument.

By default the function use the [deploy-rescaler](https://hub.docker.com/r/fjudith/deploy-rescaler) container image.
Alternatively it is possible to build yourt own image from the [function directory](./functions/deploy-rescaler).

```bash
# example
pushd functions/deploy-rescaler && \
docker image build -t fjudith/deploy-rescaler:kubeless-python3.6 . && \
docker image push fjudith/deploy-rescaler && \
popd
```

## Rescale-Replicas

The `rescale-replicas` function receives message posted by the `rescaler` website pod to restore amount of replicas that were reduced by the `downscale-replicas` function. It also restore the ingress rules modified by the `update-ingress` function.
The function is triggered by Kubeless using the remote procedure call mechanism leveraging the [HTTP Trigger](https://kubeless.io/docs/http-triggers/)

```bash
kubeless function deploy rescale-replicas \
  --namespace kubeless \
  --runtime python3.6 \
  --handler handler.handle \
  --from-file functions/rescale-replicas/handler.py \
  --dependencies functions/rescale-replicas/requirements.txt \
  --env RESCALER_NAME='rescaler' && \
kubectl -n kubeless patch deployment rescale-replicas -p '{"spec":{"template":{"spec":{"serviceAccountName":"kubeless-rescale-manage"}}}}'
```

Execute the following command to create a `trigger` that run the `rescale-replicas` function on HTTP POST events.

```bash
kubeless trigger http create --namespace kubeless rescale-replicas --function-name rescale-replicas
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
