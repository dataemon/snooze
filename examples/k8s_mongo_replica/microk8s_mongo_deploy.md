# MicroK8s Mongo Deployment
This document describes the procedure for deploying the mongodb replicaset using a MicroK8s cluster.
It's referenced from the mongodb official repo [mongodb-kubernetes-operator](https://github.com/mongodb/mongodb-kubernetes-operator/tree/master#documentation)

**Table of contents**

- [Install the Community Kubernetes Operator](#install-the-community-kubernetes-operator)
- [Deploy and Configure a MongoDBCommunity Resource](#deploy-and-configure-a-mongodbcommunity-resource)

## Install the Community Kubernetes Operator

```bash
microk8s helm repo add mongodb https://mongodb.github.io/helm-charts
microk8s helm install community-operator mongodb/community-operator

```

## Deploy and Configure a MongoDBCommunity Resource

The following steps are referenced from the official MicroK8s 

### Install XXXX

1. Install MicroK8s

On each one of your VMs run:
```bash
kubectl apply -f mongodb.com_v1_mongodbcommunity_cr.yaml
kubectl delete -f mongodb.com_v1_mongodbcommunity_cr.yaml
```

2. Join the group

MicroK8s creates a group to enable seamless usage of commands which require admin privilege. To add your current user to the group and gain access to the .kube caching directory, run the following two commands:

```bash
wget https://github.com/jqlang/jq/releases/download/jq-1.7/jq-linux-amd64
chmod +x jq-linux-amd64
sudo mv jq-linux-amd64 /usr/local/bin/jq
sudo ln -s /usr/local/bin/jq /usr/bin/jq
jq --version


kubectl get secret example-mongodb-admin-my-user -n default -o json | jq -r '.data | with_entries(.value |= @base64d)'

kubectl -n default exec --stdin --tty pod/example-mongodb-0 -- /bin/bash

# https://stackoverflow.com/questions/59367515/mongodb-connection-string-uri-not-working-in-the-kubernetes
# From within the cluster you should reference the MongoDB Pod using <service-name>.<namespace-name>.svc.cluster.local.
mongosh "mongodb+srv://my-user:test_pw_123@example-mongodb-svc.default.svc.cluster.local/admin?replicaSet=example-mongodb&ssl=false"

mongosh "mongodb://my-user:test_pw_123@example-mongodb-0.example-mongodb-svc.default.svc.cluster.local:27017,example-mongodb-1.example-mongodb-svc.default.svc.cluster.local:27017,example-mongodb-2.example-mongodb-svc.default.svc.cluster.local:27017/admin?replicaSet=example-mongodb&ssl=false"

# mongosh "mongodb://my-user:test_pw_123@example-mongodb-svc.default.svc.cluster.local/admin"
# # this also works!!!
# mongosh "mongodb://my-user:test_pw_123@localhost:27017/admin?authMechanism=SCRAM-SHA-256"
# # this works!!!
# mongosh --host localhost -u my-user -p test_pw_123 --authenticationDatabase admin
```
