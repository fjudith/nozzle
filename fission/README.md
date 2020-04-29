
# Nozzle

This document demonstrates how to deploy Nozzle in a Kubernetes cluster running the Fission serverless platform.

Serverless is a particular kind of microservices architecture that splits services into ephemeral functions to enhance observability and cost efficiency.
Serverless platforms are orchestration tools to efficiently run the code when it is required. To acheive this they support a set of trigger to react on events like HTTP requests, scheduled jobs, message queue publishing, etc.

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
  --method "POST" \
  --spec
```

---

## Teardown

```bash
fission function delete --name publish-resources

```

## Reference

* [Packaging source code](https://docs.fission.io/docs/usage/package)
* [How to develop a serverless application with Fission (part 1)](https://tachingchen.com/blog/how-to-develop-a-serverless-application-with-fission-pt-1/)
* [How to develop a serverless application with Fission (part 2)](https://tachingchen.com/blog/how-to-develop-a-serverless-application-with-fission-pt-2/)