# MicroK8s Deployment
This document describes the procedure for deploying the Snooze project using a MicroK8s cluster.

**Table of contents**

- [Build a highly available Kubernetes cluster with MicroK8s](#build-a-highly-available-kubernetes-cluster-with-microk8s)
- [Deploy Snooze on MicroK8s](#deploy-snooze-on-microk8s)

## Build a highly available Kubernetes cluster with MicroK8s

The following steps are referenced from the official MicroK8s [documentation-1](https://ubuntu.com/tutorials/getting-started-with-kubernetes-ha?&_ga=2.228013723.725207305.1695176263-1656778853.1693882766#1-overview), [documentation-2](https://microk8s.io/docs/getting-started) and [documentation-3](https://microk8s.io/docs/high-availability).

### Install MicroK8s

1. Install MicroK8s

On each one of your VMs run:
```bash
sudo snap install microk8s --classic
```

2. Join the group

MicroK8s creates a group to enable seamless usage of commands which require admin privilege. To add your current user to the group and gain access to the .kube caching directory, run the following two commands:

```bash
sudo usermod -a -G microk8s $USER
sudo chown -f -R $USER ~/.kube
```

You will also need to re-enter the session for the group update to take place:

```bash
su - $USER
```

3. Check the status

MicroK8s has a built-in command to display its status. During installation you can use the `--wait-ready` flag to wait for the Kubernetes services to initialise:

```bash
microk8s status --wait-ready
```

4. Access Kubernetes

MicroK8s bundles its own version of kubectl for accessing Kubernetes. Use it to run commands to monitor and control your Kubernetes. For example, to view your node:

```bash
microk8s kubectl get nodes
```

…or to see the running services:

```bash
microk8s kubectl get services
```

MicroK8s uses a namespaced kubectl command to prevent conflicts with any existing installs of kubectl. If you don’t have an existing install, it is easier to add an alias (append to ~/.bash_aliases) like this:

```bash
alias kubectl='microk8s kubectl'
```

5. Deploy an app

Of course, Kubernetes is meant for deploying apps and services. You can use the kubectl command to do that as with any Kuberenetes. Try installing a demo app:

```bash
microk8s kubectl create deployment nginx --image=nginx
```

It may take a minute or two to install, but you can check the status:

```bash
microk8s kubectl get pods
```

To delete the demo app:

```bash
microk8s kubectl delete deployment nginx
```

6. Use add-ons

MicroK8s uses the minimum of components for a pure, lightweight Kubernetes. However, plenty of extra features are available with a few keystrokes using “add-ons” - pre-packaged components that will provide extra capabilities for your Kubernetes, from simple DNS management to machine learning with Kubeflow!

To start it is recommended to add DNS management to facilitate communication between services. For applications which need storage, the `hostpath-storage` add-on provides directory space on the host. These are easy to set up:

```bash
microk8s enable dns
microk8s enable hostpath-storage
microk8s enable helm
```

7. Starting and Stopping MicroK8s

MicroK8s will continue running until you decide to stop it. You can stop and start MicroK8s with these simple commands:

```bash
microk8s stop
```

… will stop MicroK8s and its services. You can start again any time by running:

```bash
microk8s start
```

Note that if you leave MicroK8s running, it will automatically restart after a reboot. If you don’t want this to happen, simply remember to run microk8s stop before you power down.


### High Availability (HA)

1. Create a MicroK8s multi-node cluster

Now let’s focus on creating the Kubernetes cluster. On the initial node, run:

```bash
microk8s add-node
```

This command will give you the following output:

```bash
Join node with:
microk8s join ip-172-31-20-243:25000/DDOkUupkmaBezNnMheTBqFYHLWINGDbf

If the node you are adding is not reachable through the default interface 
you can use one of the following:
microk8s join 10.1.84.0:25000/DDOkUupkmaBezNnMheTBqFYHLWINGDbf
microk8s join 10.22.254.77:25000/DDOkUupkmaBezNnMheTBqFYHLWINGDbf
```

Copy the join command from the output and run it from the next MicroK8s node. It may take a few minutes to successfully join.

Repeat this process (generate a token, run it from the joining node) for the third node.

The same process should be repeated if you want to join additional nodes.

2. Set failure domains 
>  Available with 1.20+

To make MicroK8s failure domain aware associate an integer to each failure domain and update the `/var/snap/microk8s/current/args/ha-conf` with it. A restart of MicroK8s in the updated nodes is required (`microk8s.stop; microk8s.start`). For example:
```bash
echo "failure-domain=42" > /var/snap/microk8s/current/args/ha-conf
microk8s.stop
microk8s.start
```

3. Check the status

Run the status command:

```bash
microk8s status
```

From MicroK8s version 1.19, this will now inform you of the HA status and the addresses and roles of additional nodes. For example:

```
microk8s is running
high-availability: yes
  datastore master nodes: 10.128.63.86:19001 10.128.63.166:19001 10.128.63.43:19001
  datastore standby nodes: none
```

4. Deploy a sample containerised application

Let’s now create a microbot deployment with three pods via the kubectl cli. Run this on any of the control plane nodes:

```
microk8s kubectl create deployment microbot --image=dontrebootme/microbot:v1
microk8s kubectl scale deployment microbot --replicas=3
```

To expose our deployment we need to create a service:

```
microk8s kubectl expose deployment microbot --type=NodePort --port=80 --name=microbot-service
```

After a few minutes our cluster looks like this:

```
> microk8s kubectl get all --all-namespaces
NAMESPACE     NAME                                             READY   STATUS    RESTARTS        AGE
kube-system   pod/calico-node-qdf82                            1/1     Running   1 (6d23h ago)   7d17h
kube-system   pod/calico-kube-controllers-784587f7f-pvk92      1/1     Running   1 (6d23h ago)   15d
kube-system   pod/dashboard-metrics-scraper-5cb4f4bb9c-w6p6x   1/1     Running   1 (6d23h ago)   16d
kube-system   pod/kubernetes-dashboard-fc86bcc89-ps75k         1/1     Running   1 (6d23h ago)   16d
kube-system   pod/coredns-7745f9f87f-9tqph                     1/1     Running   1 (6d23h ago)   16d
kube-system   pod/calico-node-wm4s4                            1/1     Running   1 (6d23h ago)   7d17h
kube-system   pod/calico-node-x7kzm                            1/1     Running   1 (6d23h ago)   7d17h
kube-system   pod/hostpath-provisioner-58694c9f4b-7vqbq        1/1     Running   0               19h
default       pod/microbot-66f478bcc6-zlnmr                    1/1     Running   0               25s
default       pod/microbot-66f478bcc6-j6v6p                    1/1     Running   0               13s
default       pod/microbot-66f478bcc6-qmh8l                    1/1     Running   0               13s

NAMESPACE     NAME                                TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)                  AGE
default       service/kubernetes                  ClusterIP   10.152.183.1     <none>        443/TCP                  16d
kube-system   service/kube-dns                    ClusterIP   10.152.183.10    <none>        53/UDP,53/TCP,9153/TCP   16d
kube-system   service/kubernetes-dashboard        ClusterIP   10.152.183.107   <none>        443/TCP                  16d
kube-system   service/dashboard-metrics-scraper   ClusterIP   10.152.183.68    <none>        8000/TCP                 16d
default       service/microbot-service            NodePort    10.152.183.29    <none>        80:30913/TCP             5s

NAMESPACE     NAME                         DESIRED   CURRENT   READY   UP-TO-DATE   AVAILABLE   NODE SELECTOR            AGE
kube-system   daemonset.apps/calico-node   3         3         3       3            3           kubernetes.io/os=linux   16d

NAMESPACE     NAME                                        READY   UP-TO-DATE   AVAILABLE   AGE
kube-system   deployment.apps/coredns                     1/1     1            1           16d
kube-system   deployment.apps/kubernetes-dashboard        1/1     1            1           16d
kube-system   deployment.apps/dashboard-metrics-scraper   1/1     1            1           16d
kube-system   deployment.apps/calico-kube-controllers     1/1     1            1           16d
kube-system   deployment.apps/hostpath-provisioner        1/1     1            1           19h
default       deployment.apps/microbot                    3/3     3            3           25s

NAMESPACE     NAME                                                   DESIRED   CURRENT   READY   AGE
kube-system   replicaset.apps/coredns-7745f9f87f                     1         1         1       16d
kube-system   replicaset.apps/kubernetes-dashboard-fc86bcc89         1         1         1       16d
kube-system   replicaset.apps/dashboard-metrics-scraper-5cb4f4bb9c   1         1         1       16d
kube-system   replicaset.apps/calico-kube-controllers-6c99c8747f     0         0         0       16d
kube-system   replicaset.apps/calico-kube-controllers-784587f7f      1         1         1       15d
kube-system   replicaset.apps/hostpath-provisioner-58694c9f4b        1         1         1       19h
default       replicaset.apps/microbot-66f478bcc6                    3         3         3       25s
```

At the very top, we have the microbot pods, `service/microbot-service` is the second in the services list. Our service has a cluster IP through which we can access it. Notice, however, that our service is of type [NodePort](https://kubernetes.io/docs/concepts/services-networking/service/#nodeport). This means that our deployment is also available on a port on the host machine; that port is randomly selected and in this case, it happens to be 30913. 

5. Access the application from your browser

We can now open a browser, point it to `127.0.0.1:30913/` and marvel at our microbot!

![Image_microbot](./figs/Annotation_2023-09-22_121701.png)


## Deploy Snooze on MicroK8s

The Snooze was previously deployed as a cluster using [Docker Swarm](https://docs.docker.com/engine/swarm/).


### Addon: dashboard
[dashboard-proxy document](https://microk8s.io/docs/command-reference#heading--microk8s-dashboard-proxy)

```bash
> microk8s dashboard-proxy
Checking if Dashboard is running.
Infer repository core for addon dashboard
Waiting for Dashboard to come up.
Trying to get token from microk8s-dashboard-token
Waiting for secret token (attempt 0)
Dashboard will be available at https://127.0.0.1:10443
Use the following token to login:
eyJhbGciOiJSUzI1NiIsImtpZCI6IlI2Rkc0YkQzamQwdm1sOHZvYnNYbE9fY0tQTUdZR0RIM2FkTi1zazN4MlEifQ.eyJpc3MiOiJrdWJlcm5ldGVzL3NlcnZpY2VhY2NvdW50Iiwia3ViZXJuZXRlcy5pby9zZXJ2aWNlYWNjb3VudC9uYW1lc3BhY2UiOiJrdWJlLXN5c3RlbSIsImt1YmVybmV0ZXMuaW8vc2VydmljZWFjY291bnQvc2VjcmV0Lm5hbWUiOiJtaWNyb2s4cy1kYXNoYm9hcmQtdG9rZW4iLCJrdWJlcm5ldGVzLmlvL3NlcnZpY2VhY2NvdW50L3NlcnZpY2UtYWNjb3VudC5uYW1lIjoiZGVmYXVsdCIsImt1YmVybmV0ZXMuaW8vc2VydmljZWFjY291bnQvc2VydmljZS1hY2NvdW50LnVpZCI6ImEwMDU5Y2VlLTUxMDAtNGQxNi04N2I0LWVlNGQ3NDgxYTE2MiIsInN1YiI6InN5c3RlbTpzZXJ2aWNlYWNjb3VudDprdWJlLXN5c3RlbTpkZWZhdWx0In0.JdMIspZ2LwmmhNnf3_TE6ezZk8lkG89UKIgZ0jQ4ygisSIHrkrkZIN4TIr1e-FjTTtIFZl10jvf4JQTUtgahBGhFaezgJGj4kkfnNaG2wB0bO8FJP_IeQD7sspspAHZEKWHQ0VmTB5b5PzamrTNVQyXqnsZt8E0iXnjasV1rqxqVSQZA3Rx28XBb7fgdE5ekh682G3qZ9ELnxBPGqH6XlGArdAXIjTZsNtE-rxFcu7zBvJLc6U5HQPhdG7EuZsU_u9YWWHqImItd3bJVzoIPTsK9PgBD5-QIchrE45VzuXKQ0ETxlaCsVrIMFScp3i8NXxpie1ekm3iqVzm4R5K_nA
```
![dashboard-proxy](./figs/Annotation_2023-09-28_153124.png)






