import json
import random
import time
import argparse
import signal
from datetime import datetime
from confluent_kafka import Producer

# --- Kafka Configuration ---
conf = {
    'bootstrap.servers': 'localhost:9092',
    'client.id': 'event-generator',
}
producer = Producer(conf)

# --- Graceful Shutdown ---
running = True
def signal_handler(sig, frame):
    global running
    print("\n🛑 Caught interrupt. Exiting...")
    running = False
signal.signal(signal.SIGINT, signal_handler)

# --- Utility to serialize structured keys ---
def serialize_key(key):
    return json.dumps(key) if isinstance(key, dict) else str(key)

# --- Kafka Delivery Callback ---
def delivery_report(err, msg):
    if err is not None:
        print(f"❌ Delivery failed: {err}")
    else:
        print(f"✔️ Sent to {msg.topic()} [{msg.partition()}] offset {msg.offset()}")

# --- Schema Functions ---
def generate_events_user():
    user_id = f"user-{random.randint(1, 1000)}"
    event_type = random.choice(["click", "view", "purchase"])
    timestamp = datetime.utcnow().isoformat() + "Z"
    return {
        "key": {"user_id": user_id, "source": "web"},
        "headers": {
            "env": "prod",
            "source": "events-user-gen"
        },
        "payload": {
            "event_type": event_type,
            "timestamp": timestamp,
            "source": "web",

            "meta": {"trace_id": f"trace-{random.randint(1000, 9999)}"},
            "user": {
                "id": user_id,
                "profile": {
                    "active": random.choice([True, False]),
                    "age": random.randint(18, 70),
                    "preferences": {
                        "lang": "en",
                        "categories": ["news", "sports"]
                    }
                }
            },
            "event": {"type": event_type}
        }
    }

def generate_notifications_user():
    user_id = f"user-{random.randint(1, 1000)}"
    timestamp = datetime.utcnow().isoformat() + "Z"
    notification_type = random.choice(["push", "email"])
    return {
        "key": user_id,
        "headers": {
            "env": "staging",
            "source": "notifications-gen"
        },
        "payload": {
            "timestamp": timestamp,
            "notification_type": notification_type,
            "channel": "sms",

            "notification": {
                "id": f"notif-{random.randint(1000, 9999)}",
                "content": {"title": "Welcome", "body": "Check this out"},
                "timestamp": timestamp
            },
            "receiver": {"id": user_id}
        }
    }

def generate_orders_user():
    order_id = f"order-{random.randint(10000, 99999)}"
    timestamp = datetime.utcnow().isoformat() + "Z"
    status = random.choice(["placed", "shipped", "delivered"])
    tier = random.choice(["gold", "silver", "bronze"])
    return {
        "key": {"order_id": order_id},
        "headers": {
            "env": "prod",
            "source": "orders-gen",
            "tier": tier
        },
        "payload": {
            "timestamp": timestamp,
            "order_status": status,
            "tier": tier,

            "order": {
                "id": order_id,
                "status": status,
                "items": [{"sku": f"sku-{i}", "qty": random.randint(1, 5)} for i in range(3)],
                "total": round(random.uniform(100, 1000), 2),
                "timestamp": timestamp
            }
        }
    }

# --- Topic Configuration ---
TOPIC_PREFIXES = {
    "events_user": {
        "suffixes": ["raw", "audit"],
        "schema_fn": generate_events_user
    },
    "notifications_user": {
        "suffixes": ["raw"],
        "schema_fn": generate_notifications_user
    },
    "orders_user": {
        "suffixes": ["raw"],
        "schema_fn": generate_orders_user
    }
}

# --- Main Event Loop ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kafka Multi-Topic Event Generator")
    parser.add_argument("--eps", type=int, default=1000, help="Events per second")
    args = parser.parse_args()
    interval = 1.0 / args.eps
    total_events = 0

    # Build topic list
    all_topics = [
        (f"{prefix}.{suffix}", cfg["schema_fn"])
        for prefix, cfg in TOPIC_PREFIXES.items()
        for suffix in cfg["suffixes"]
    ]

    print(f"🚀 Generating events at {args.eps} EPS. Press Ctrl+C to stop.")

    try:
        while running:
            topic, schema_fn = random.choice(all_topics)
            event = schema_fn()

            key = serialize_key(event["key"])
            value = json.dumps(event["payload"])
            kafka_headers = [(k, str(v).encode("utf-8")) for k, v in event.get("headers", {}).items()]

            producer.produce(
                topic=topic,
                key=key,
                value=value,
                headers=kafka_headers,
                callback=delivery_report
            )
            producer.poll(0)
            total_events += 1
            time.sleep(interval)

    finally:
        producer.flush()
        print(f"\n✅ Sent {total_events} events. Shutdown complete.")
