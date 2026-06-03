import asyncio
from aiokafka import AIOKafkaConsumer
import asyncpg
import os, json, subprocess
from minio import Minio

BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
GROUP_ID = "genomic-indexer-group"
MINIO = Minio("minio:9000", ...)  # reuse

async def process_message(msg):
    data = json.loads(msg.value)
    # Download from MinIO
    bucket = "genomic-data"
    obj = data["object_path"]
    local_file = f"/tmp/{os.path.basename(obj)}"
    MINIO.fget_object(bucket, obj, local_file)
    
    # Determine indexing command
    ftype = data["file_type"]
    index_path = None
    if ftype in ["text/x-fasta", "text/plain"] and obj.endswith((".fa",".fasta")):
        subprocess.run(["samtools", "faidx", local_file], check=True)
        index_path = local_file + ".fai"
    elif ftype in ["application/x-gzip"] and obj.endswith(".vcf.gz"):
        # Already compressed; create index
        subprocess.run(["tabix", "-p", "vcf", local_file], check=True)
        index_path = local_file + ".tbi"
    elif obj.endswith(".bam"):
        subprocess.run(["samtools", "index", local_file], check=True)
        index_path = local_file + ".bai"
    # FASTQ usually not indexed, skip; or create BWA index...
    
    if index_path:
        # Upload index back to MinIO
        index_obj = obj + ".index"
        MINIO.fput_object(bucket, index_obj, index_path)
        # Insert into PostgreSQL
        conn = await asyncpg.connect(dsn="postgresql://genomics:...@postgres:5432/genomics")
        await conn.execute("""
            INSERT INTO file_versions (tenant, filename, sha256, object_key, index_key, file_size, uploaded_by, created_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,NOW())
        """, data["tenant"], data["filename"], data["sha256"], obj, index_obj, data["size"], data["user_id"])
        await conn.close()

async def main():
    consumer = AIOKafkaConsumer("file.uploaded", bootstrap_servers=BROKER, group_id=GROUP_ID)
    await consumer.start()
    try:
        async for msg in consumer:
            await process_message(msg)
    finally:
        await consumer.stop()

if __name__ == "__main__":
    asyncio.run(main())
