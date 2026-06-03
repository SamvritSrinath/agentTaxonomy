from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
import os, hashlib, magic
from minio import Minio
from kafka import KafkaProducer
import json
import aiokafka
from validate import validate_genomic_file

app = FastAPI()

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
UPLOAD_TOPIC = "file.uploaded"

minio_client = Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=False)

producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER,
                         value_serializer=lambda v: json.dumps(v).encode('utf-8'))

@app.post("/upload")
async def upload(
    tenant: str,
    user_id: str,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    # 1. Validate file type and integrity
    content = await file.read()
    file_type = magic.from_buffer(content, mime=True)
    if not validate_genomic_file(file_type, file.filename):
        raise HTTPException(status_code=400, detail="Invalid genomic file")
    
    # 2. Compute SHA256 for versioning
    sha256 = hashlib.sha256(content).hexdigest()
    
    # 3. Store in MinIO with tenant isolation and version
    object_name = f"{tenant}/{file.filename}/versions/{sha256}/{file.filename}"
    bucket_name = "genomic-data"
    if not minio_client.bucket_exists(bucket_name):
        minio_client.make_bucket(bucket_name)
    minio_client.put_object(bucket_name, object_name, content, len(content))
    
    # 4. Publish event to Kafka
    event = {
        "tenant": tenant,
        "user_id": user_id,
        "filename": file.filename,
        "sha256": sha256,
        "object_path": object_name,
        "file_type": file_type,
        "size": len(content)
    }
    producer.send(UPLOAD_TOPIC, value=event)
    producer.flush()
    
    return {"status": "uploaded", "sha256": sha256, "object": object_name}
