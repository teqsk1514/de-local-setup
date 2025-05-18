```shell
curl -X DELETE http://localhost:8083/connectors/mongo-source
```

```shell
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "mongo-source",
    "config": {
      "connector.class": "io.debezium.connector.mongodb.MongoDbConnector",
      "tasks.max": "2",
      "mongodb.connection.string": "mongodb://mongos:27017",
      "mongodb.name": "mongo_debezium_raw",
      "capture.mode": "change_streams",
      "topic.prefix": "debezium.oplogs.raw",
      "tombstones.on.delete" : "false",
      "topic.naming.strategy": "io.debezium.schema.OnlyPrefixTopicNamingStrategy",
      "snapshot.mode": "no_data",
      "key.converter": "org.apache.kafka.connect.json.JsonConverter",
      "value.converter": "org.apache.kafka.connect.json.JsonConverter",
      "key.converter.schemas.enable": "false",
      "value.converter.schemas.enable": "false"
      }
  }'
```