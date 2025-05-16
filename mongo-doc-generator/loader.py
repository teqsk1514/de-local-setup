import asyncio
import random
import string
import yaml
import logging
import signal
from datetime import datetime
from bson import ObjectId, Decimal128
from motor.motor_asyncio import AsyncIOMotorClient
from collections import defaultdict, deque

# ───── Logging Setup ───── #
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("MongoLoader")

# ───── Config Load ───── #
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

mongo_uri = config["mongo_uri"]
rps = config["rps"]
doc_size = config["document_size"]
mode = config.get("mode", "benchmark")
duration = config.get("duration_seconds", 60)
db_collection_map = config["db_collection_map"]
op_weights = config.get("operations", {"insert": 1.0})

# Assert sum of weights is approximately 1.0
assert abs(sum(op_weights.values()) - 1.0) < 1e-6, "Operation weights must sum to 1.0"

# ───── MongoDB Client ───── #
client = AsyncIOMotorClient(mongo_uri)
stop_signal = False

# ───── Document ID Tracking ───── #
doc_id_map = defaultdict(lambda: deque(maxlen=10000))

def generate_random_value():
    return {
        "string": ''.join(random.choices(string.ascii_letters, k=20)),
        "int": random.randint(1, 1000),
        "float": random.random(),
        "bool": random.choice([True, False]),
        "array": [random.randint(0, 100) for _ in range(5)],
        "object": {"x": random.randint(1, 10)},
        "date": datetime.utcnow(),
        "objectId": ObjectId(),
        "null": None,
        "decimal": Decimal128("123.45"),
    }

def generate_document(target_size):
    base_doc = generate_random_value()
    while len(str(base_doc).encode()) < target_size:
        key = ''.join(random.choices(string.ascii_letters, k=5))
        base_doc[key] = generate_random_value()
    return base_doc

async def op_worker(db_name, coll_name):
    logger.info(f"📤 Starting ops: db='{db_name}' collection='{coll_name}' @ {rps} RPS")
    db = client[db_name]
    coll = db[coll_name]
    interval = 1 / rps
    inserted = updated = deleted = failed = 0
    start_time = datetime.now()
    key = f"{db_name}.{coll_name}"
    operations = list(op_weights.keys())
    weights = list(op_weights.values())

    async def log_metrics():
        while not stop_signal:
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > 0:
                logger.info(
                    f"📊 {key}: "
                    f"Inserted={inserted}, Updated={updated}, Deleted={deleted}, Failed={failed}, "
                    f"Rate={(inserted + updated + deleted) / elapsed:.2f}/s"
                )
            await asyncio.sleep(10)

    asyncio.create_task(log_metrics())

    try:
        while not stop_signal:
            op_type = random.choices(operations, weights)[0]
            try:
                if op_type == "insert":
                    doc = generate_document(doc_size)
                    result = await coll.insert_one(doc)
                    doc_id_map[key].append(result.inserted_id)
                    inserted += 1

                elif op_type == "update" and doc_id_map[key]:
                    index = int(random.random() ** 2 * len(doc_id_map[key]))  # skew to recent
                    target_id = doc_id_map[key][-(index + 1)]
                    update_doc = {
                        "$set": {
                            "updatedAt": datetime.utcnow(),
                            "status": random.choice(["active", "inactive", "pending"])
                        }
                    }
                    result = await coll.update_one({"_id": target_id}, update_doc)
                    updated += result.modified_count

                elif op_type == "delete" and doc_id_map[key]:
                    target_id = doc_id_map[key].popleft()  # remove oldest
                    result = await coll.delete_one({"_id": target_id})
                    deleted += result.deleted_count

            except Exception as e:
                failed += 1
                logger.error(f"❌ {op_type.upper()} error in {key}: {e}")

            await asyncio.sleep(interval)

    except asyncio.CancelledError:
        pass
    finally:
        logger.info(f"🛑 Worker exit: {key} | Inserted={inserted}, Updated={updated}, Deleted={deleted}, Failed={failed}")

async def benchmark_mode():
    logger.info("🚀 Benchmark mode active.")
    end_time = asyncio.get_event_loop().time() + duration
    tasks = []
    for db_name, collections in db_collection_map.items():
        for coll_name in collections:
            task = asyncio.create_task(op_worker(db_name, coll_name))
            tasks.append(task)

    while asyncio.get_event_loop().time() < end_time:
        await asyncio.sleep(1)

    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("✅ Benchmark complete.")

async def long_running_mode():
    logger.info("🌀 Long-running mode active. Use Ctrl+C to stop.")
    tasks = []
    for db_name, collections in db_collection_map.items():
        for coll_name in collections:
            task = asyncio.create_task(op_worker(db_name, coll_name))
            tasks.append(task)

    while not stop_signal:
        await asyncio.sleep(1)

    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("✅ Shutdown complete.")

def handle_sigterm(signum, frame):
    global stop_signal
    logger.warning("📦 Caught termination signal. Exiting gracefully...")
    stop_signal = True

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_sigterm)
    signal.signal(signal.SIGTERM, handle_sigterm)

    try:
        if mode == "benchmark":
            asyncio.run(benchmark_mode())
        elif mode == "long_running":
            asyncio.run(long_running_mode())
        else:
            raise ValueError(f"Unknown mode: {mode}")
    except Exception as ex:
        logger.exception(f"💥 Fatal error: {ex}")
