rs.initiate({_id: "configReplSet", configsvr: true, members: [{ _id : 0, host : "configsvr:27017" }]});
sleep(5000);
rs.initiate({_id: "shard1ReplSet", members: [{ _id : 0, host : "shard1:27017" }]});
rs.initiate({_id: "shard2ReplSet", members: [{ _id : 0, host : "shard2:27017" }]});
sh.addShard("shard1ReplSet/shard1:27017");
sh.addShard("shard2ReplSet/shard2:27017");
sh.enableSharding("db1");
sh.shardCollection("db1.events.logs", { "_id": 1 });
