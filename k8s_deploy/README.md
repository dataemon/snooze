
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

docker exec -it $(docker ps -qf label=com.docker.swarm.service.name=snoozeweb_mongo1) /bin/bash -c "echo '${replicate}' | mongo"

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