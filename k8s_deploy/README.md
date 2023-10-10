
### Docker deployment

1. Simple

deploy one single web service
```bash
sudo docker run --name snooze-db -d mongo:4.2.3
export DATABASE_URL=mongodb://db:27017/snooze
sudo docker run --name snoozeweb -e DATABASE_URL=$DATABASE_URL \
    --link snooze-db:db -d -p 5200:5200 snoozeweb/snooze
sudo docker rm -f snoozeweb snooze-db
```

2. Advanced

deploy one single web service
```bash
sudo docker stack deploy -c docker-compose.yaml snoozeweb
# Wait until MongoDB containers are up

replicate="rs.initiate(); sleep(1000); cfg = rs.conf(); cfg.members[0].host = \"mongo1:27017\"; rs.reconfig(cfg); rs.add({ host: \"mongo2:27017\", priority: 0.5 }); rs.add({ host: \"mongo3:27017\", priority: 0.5 }); rs.status();"

sudo docker exec -it $(sudo docker ps -qf label=com.docker.swarm.service.name=snoozeweb_mongo1) /bin/bash -c "echo '${replicate}' | mongo"

sudo docker service ls


sudo docker stack rm snoozeweb

```