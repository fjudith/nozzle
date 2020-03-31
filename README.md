# Nozzle

Reduce Kubernetes workload on scheduled or traffic decision basis and restore workload on-demand via Web UI or http trigger.

### Screeshots

![Grafana footprint](./docs/img/grafana_downscale.png)

![Rescaler Web UI](./docs/img/rescaler.png)

![Rescaler footprint](./docs/img/grafana_rescaler.png)

![Rescaling footprint](./docs/img/grafana_rescale.png)

## Backup efficiency

The last-known Kubernetes resources configuration is backed up as [annotations](https://kubernetes.io/docs/concepts/overview/working-with-objects/annotations/), **only** if the native `kubectl.kubernetes.io/last-applied-configuration`  is not present.

Following additional annotations are implement depending on the ressource type:

* **Deployment & Statefulset**: `replicas.noozle.io/last-known-configuration`
* **Ingress**: `rules.noozle.io/last-known-configuration`

**Warning** : Ingress resources are modified to redirect the traffic to the `rescaler` pod

## Message formats

* **Replicas JSON**: `{"namespace": str, "name": str, "kind": str, "replicas": int, "selector": { dict }}`
* **Ingress JSON**: `{"namespace": str, "name": str, "rules": { dict }}`

## Implementations

### Kubeless

Serverless implementation based on Python3, Kubeless and NATS.

### OpenFaaS

Serverless implementation based on Python3, OpenFaaS and NATS.

### Dapr

Serverless implementation based on Python3, Dapr and NATS.

### Golang

Native Kubernetes implementation based on a Custom Controller written and Go `1.13.x`.

```plantuml
@startuml

actor "user"
participant "publish-replicas"
database "kubernetes"
queue "nats"
participant "downscale-replicas"
participant "inject-rescaler"
participant "update-ingress"
queue "stan"
entity "rescaler"

== Inventory ==
"publish-replicas" -> "kubernetes" : List namespaces labeled \n ""nozzle=true""
"kubernetes" --> "publish-replicas" : Eligible workload replicas (deploy/sts)
"publish-replicas" -> "nats": Publish to **k8s_replicas** topic

== Downscale ==
"downscale-replicas" -> "nats": Subscribe **k8s_replicas** topic
"nats" --> "downscale-replicas": Replicas JSON
"downscale-replicas" -> "kubernetes": Reduce replicas: \n""deploy = 0, sts = 1""

== Redirect ==
"update-ingress" -> "nats": Subscribe **k8s_replicas** topic
"nats" --> "update-ingress": Replicas JSON
"update-ingress" -> "stan": Publish matched selector \n ingress spec to topic **k8s_ingress** topic
"update-ingress" -> "kubernetes": Change ingress target
|||
"inject-rescaler" -> "nats": Subscribe **k8s_replicas** topic
"nats" -> "inject-rescaler": Replicas JSON
"inject-rescaler" -> "kubernetes": Deploy on-demand replicas rescaler 
"kubernetes" --> "rescaler": Run Web server

== User action ==
"user" -> "rescaler": Request rescale

== Rescale ==
"rescale-replicas" -> "stan": Subscribe **k8s_ingresses**
"rescaler" -> "rescale-replicas": Request rescaling
"stan" --> "rescale-replicas": Select ingress
"rescale-replicas" -> "kubernetes": Restore replicas
"rescale-replicas" -> "kubernetes": Restore ingress
"rescale-replicas" -> "kubernetes": Remove rescaler
"kubernetes" --> "rescaler": Delete rescaler resources (deploy, svc)
@enduml
```