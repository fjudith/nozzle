# Nozzle

## Pre-requesits

Argo requires you to install the [Argo client](https://github.com/argoproj/argo/releases) in order to deploy the workflow
You will also need to get a copy of this repository to run the commands:

```bash
git clone https://github.com/fjudith/nozzle

cd nozzle/argo
```

## Manifests

The [manifests](./manifests/) directory contains the required [RBAC and ServiceAccounts](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) enabling each function to interact with the Kubernetes API.
It also contain an application running 3 replicas of the [nginx-alpine](https://hub.docker.com/r/amd64/nginx) image in the form of Deployment and Statefulset to demonstrate Nozzle concepts.

```bash
kubectl apply -f manifests/
```

## Worflow steps

### Publish-Resources

Run the following command line to build the `publish-resources` container.

```bash
pushd steps/publish-resources && \
docker image build -t fjudith/publish-resources:argo-python3.6 . && \
docker image push fjudith/publish-resources:argo-python3.6 && \
popd
```

### Downscale-Replicas

Run the following command line to build the `downscale-replicas` container.

```bash
pushd steps/downscale-replicas && \
docker image build -t fjudith/downscale-replicas:argo-python3.6 . && \
docker image push fjudith/downscale-replicas:argo-python3.6 && \
popd
```

### Update-Ingress

Run the following command line to build the `update-ingress` container.

```bash
pushd steps/update-ingress && \
docker image build -t fjudith/update-ingress:argo-python3.6 . && \
docker image push fjudith/update-ingress:argo-python3.6 && \
popd
```

### Deploy-Rescaler

Run the following command line to build the `deploy-rescaler` container.

```bash
pushd steps/deploy-rescaler && \
docker image build -t fjudith/deploy-rescaler:argo-python3.6 . && \
docker image push fjudith/deploy-rescaler:argo-python3.6 && \
popd
```

### Rescale-Replicas

Run the following command line to build the `rescale-replicas` container.

```bash
pushd steps/rescale-replicas && \
docker image build -t fjudith/rescale-replicas:argo-python3.6 . && \
docker image push fjudith/rescale-replicas:argo-python3.6 && \
popd
```
