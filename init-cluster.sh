#!/bin/bash

echo "⏳ Waiting for all containers to be up..."
sleep 10

echo "⚙️  Initiating Config Server ReplicaSet..."
docker exec configsvr01 mongosh --port 27019 --eval '
rs.initiate({
  _id: "configReplSet",
  configsvr: true,
  members: [{ _id: 0, host: "configsvr01:27019" }]
})
'

echo "⚙️  Initiating Shard 1 ReplicaSet..."
docker exec shard01 mongosh --port 27018 --eval '
rs.initiate({
  _id: "shard01ReplSet",
  members: [{ _id: 0, host: "shard01:27018" }]
})
'

echo "⚙️  Initiating Shard 2 ReplicaSet..."
docker exec shard02 mongosh --port 27020 --eval '
rs.initiate({
  _id: "shard02ReplSet",
  members: [{ _id: 0, host: "shard02:27020" }]
})
'

echo "⏱️  Waiting for mongos to connect to config..."
sleep 10

echo "🔗 Adding shards to mongos..."
docker exec mongos mongosh --port 27017 --eval '
sh.addShard("shard01ReplSet/shard01:27018");
sh.addShard("shard02ReplSet/shard02:27020");
sh.status();
'
