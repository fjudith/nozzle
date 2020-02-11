# Nozzle

Reduce Kubernetes resources on a metrics and scheduled decision basis.

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
"publish-replicas" -> "kubernetes" : List namespaces labeled \n **nightly-shutdown=true**
"kubernetes" --> "publish-replicas" : Eligible workload replicas (deploy/sts)
"publish-replicas" -> "nats": Publish to **k8s_replicas** topic

== Downscale ==
"downscale-replicas" -> "nats": Subscribe **k8s_replicas** topic
"nats" --> "downscale-replicas": Replicas JSON
"downscale-replicas" -> "kubernetes": Reduce replicas: \n**deploy = 0**, **sts = 1**

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

## Kubeless

Serverless implementation based on Python3, Kubeless and NATS.

## OpenFaaS

Serverless implementation based on Python3, Kubeless and NATS.

## Golang

Native Kubernetes implementation based on a Custom Controller written and Go `1.13.x`.
