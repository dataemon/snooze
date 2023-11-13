
### Docker deployment

1. Simple

deploy one single web service
```bash
# sudo docker run --name snooze-db -d mongo
sudo docker run --name snooze-db -d mongo:6.0.11
export DATABASE_URL=mongodb://db:27017/snooze
sudo docker run --name snoozeweb -e DATABASE_URL=$DATABASE_URL \
    --link snooze-db:db -d -p 5200:5200 snoozeweb/snooze
sudo docker rm -f snoozeweb snooze-db
```

2. Advanced

deploy one single web service
```bash
source .env `or` . .env
echo $HOST1
echo $HOST2
echo $HOST3
export HOST1
export HOST2
export HOST3
# https://learnubuntu.com/export-command/


docker stack deploy -c docker-compose.yaml snoozeweb
# Wait until MongoDB containers are up

replicate="rs.initiate(); sleep(1000); cfg = rs.conf(); cfg.members[0].host = \"mongo1:27017\"; rs.reconfig(cfg); rs.add({ host: \"mongo2:27017\", priority: 0.5 }); rs.add({ host: \"mongo3:27017\", priority: 0.5 }); rs.status();"

docker exec -it $(docker ps -qf label=com.docker.swarm.service.name=snoozeweb_mongo1) /bin/bash -c "echo '${replicate}' | mongosh"

docker service ls

docker service ps snoozeweb_lb --no-trunc
docker service ps snoozeweb_snooze1 --no-trunc
docker service ps snoozeweb_snooze2 --no-trunc
docker service inspect snoozeweb_lb

docker stack rm snoozeweb

docker network list
caf76666d9bf        snoozenw              bridge              local

docker network rm caf76666d9bf
```

### set sysylog

```bash
sudo chmod 777 /opt/
conda create -p /opt/snooze/ python=3.9




cd /opt
git clone https://github.com/snoozeweb/snooze_client.git
cd snooze_client
sudo /opt/snooze/bin/pip install .

sudo /opt/snooze/bin/pip install python-dateutil

sudo /opt/snooze/bin/pip install git+https://github.com/snoozeweb/snooze_plugins.git#subdirectory=input/syslog


sudo vim /etc/systemd/system/snooze-syslog.service
--------
[Unit]
Description=Snooze syslog input plugin
After=network.target

[Service]
User=snooze
ExecStart=/opt/snooze/bin/snooze-syslog
Restart=always

[Install]
WantedBy=multi-user.target
Alias=snooze-syslog.service
-------

sudo systemctl status network.target

sudo systemctl daemon-reload
sudo systemctl enable snooze-syslog.service
sudo systemctl start snooze-syslog.service

sudo systemctl status snooze-syslog.service
sudo systemctl restart snooze-syslog.service
sudo systemctl restart snooze-syslog.service
sudo systemctl stop snooze-syslog.service

sudo /opt/snooze/bin/snooze-syslog
sudo ps aux | grep snooze-syslog

sudo vim /etc/snooze/syslog.yaml
---
#################
# General options
#################

# `listening_address`: Address to listen to.
listening_address: 0.0.0.0

# `listening_port`: Port to listen to. Please note than when choosing a port
# lower than 1024 (like 514 for instance), you will need to run the process as root.
listening_port: 1514

################
# Worker options
################

# `parse_workers`: Number of threads to use for parsing.
parse_workers: 4

# `send_workers`: Number of threads to use for sending to snooze server.
send_workers: 4



sudo vim /etc/snooze/client.yaml

# /etc/snooze/client.yaml
---
server: http://10.146.16.30:80


```


### docker deployment problems

0. docker deployment is ok.
1. Web access is very slow after a prolonged period of inactivity.
2. The Kubernetes service on the lab cloud VMs is currently inaccessible.

### debug findings 

1. microk8s have memery limit for 4G. According to this [page](https://microk8s.io/docs/getting-started#:~:text=What%20you'll%20need,-An%20Ubuntu%2022.04&text=MicroK8s%20runs%20in%20as%20little,space%20and%204G%20of%20memory.). Reminded by this [answer](https://stackoverflow.com/questions/46826164/kubernetes-pods-failing-on-pod-sandbox-changed-it-will-be-killed-and-re-create)


