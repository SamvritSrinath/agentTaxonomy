import os, json, subprocess, tempfile
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from minio import Minio
import asyncpg

SEARCH_TOPIC_IN = "search.requested"
RESULT_TOPIC = "search.completed"

producer = AIOKafkaProducer(bootstrap_servers=os.getenv("KAFKA_BROKER"))
consumer = AIOKafkaConsumer(SEARCH_TOPIC_IN, ...)

async def run_blast(query_seq, db_name, task_type="blastn"):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.fa') as f:
        f.write(f">query\n{query_seq}\n")
        f.flush()
        cmd = ["blastn", "-db", db_name, "-query", f.name, "-outfmt", "15"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout

async def process_search(msg):
    req = json.loads(msg.value)
    query = req["sequence"]
    db = req.get("db", "refseq_genomic")
    tenant = req["tenant"]
    # Run BLAST
    result = await run_blast(query, db)
    # Store result in MinIO (or PostgreSQL)
    result_key = f"{tenant}/searches/{req['job_id']}/result.json"
    minio_client.put_object("genomic-data", result_key, result, len(result))
    # Update job status in PostgreSQL
    conn = await asyncpg.connect(...)
    await conn.execute("UPDATE search_jobs SET status='completed', result_key=$1 WHERE job_id=$2", result_key, req["job_id"])
    await conn.close()
    # Send result event
    await producer.send(RESULT_TOPIC, {"job_id": req["job_id"], "result_key": result_key})

if __name__ == "__main__":
    # Run consumer loop
