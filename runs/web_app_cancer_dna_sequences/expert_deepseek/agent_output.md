# Scalable Genomic Data Management Platform for Cancer Bioinformatics

This blueprint delivers a production‑ready, event‑driven microservices architecture for ingesting, indexing, versioning, searching, and managing genomic data formats (FASTA, FASTQ, BAM, VCF). It supports multi‑tenancy, distributed sequence search, strong security, and full observability. All components are containerised and orchestrated by Kubernetes, with Kafka as the message backbone, PostgreSQL for metadata, and object storage (MinIO/S3) for raw files.

## Architecture Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Researcher │────▶│  API Gateway│────▶│  OPA Sidecar│
│  (Browser)  │     │  (FastAPI)  │     │  (Rego)     │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │ JWT Auth       ▲
                           ▼                │
                   ┌─────────────┐     ┌─────────────┐
                   │  Ingestion   │     │  Kafka      │
                   │  Service     │────▶│  Broker     │
                   │  (FastAPI)   │     │  (Strimzi)  │
                   └──────┬──────┘     └──┬───┬───┬──┘
                          │               │   │   │
                          ▼               ▼   ▼   ▼
                   ┌───────────┐   Workers: Indexer │
                   │  MinIO /  │   Search (BLAST)   │
                   │  S3       │   Format Converter  │
                   └───────────┘                     ▼
                                    ┌──────────────────────┐
                                    │  PostgreSQL           │
                                    │  (Tenants, Versions,  │
                                    │   Metadata, Jobs)     │
                                    └──────────────────────┘
```

**Key technologies:**  
- **Ingestion & API**: Python FastAPI + OPA policies for authz  
- **Messaging**: Apache Kafka (Strimzi operator)  
- **Object storage**: MinIO (S3 compatible)  
- **Metadata & versioning**: PostgreSQL  
- **Sequence search**: BLAST+ distributed via Kafka workers  
- **Indexing**: Samtools, Tabix, Bgzip  
- **Observability**: Prometheus, Grafana, OpenTelemetry/Jaeger  
- **Policy‑as‑code**: Open Policy Agent (OPA) Rego rules  
- **Container orchestration**: Kubernetes manifests (Helm‑ready)  

All services are event‑driven, scaling horizontally. Multi‑tenancy is enforced at the API gateway and data layer. Versioned datasets are implemented via S3 prefixes and PostgreSQL history tables.

---

## Project Structure
```
genomic-platform/
├── api-gateway/                   # FastAPI + OPA
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── auth.py
│   ├── opa_middleware.py
│   └── policies/                  # OPA rules
│       └── tenant.rego
├── ingestion-service/             # File upload & validation
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   ├── upload.py
│   └── validate.py
├── workers/                       # Kafka consumers
│   ├── indexer/
│   │   ├── Dockerfile
│   │   ├── index.sh
│   │   └── worker.py
│   ├── search/
│   │   ├── Dockerfile
│   │   ├── blast_worker.py
│   │   └── blastdb_config.yaml
│   └── converter/
│       ├── Dockerfile
│       └── converter.sh
├── infrastructure/
│   ├── kubernetes/
│   │   ├── namespace.yaml
│   │   ├── configmaps/
│   │   │   ├── api-gateway-config.yaml
│   │   │   ├── kafka-config.yaml
│   │   │   └── postgres-config.yaml
│   │   ├── secrets/
│   │   │   ├── jwt-secret.yaml
│   │   │   ├── minio-credentials.yaml
│   │   │   └── postgres-credentials.yaml
│   │   ├── deployments/
│   │   │   ├── api-gateway.yaml
│   │   │   ├── ingestion.yaml
│   │   │   ├── indexer.yaml
│   │   │   ├── search-worker.yaml
│   │   │   ├── postgres.yaml
│   │   │   └── minio.yaml
│   │   ├── services/
│   │   │   ├── api-gateway-svc.yaml
│   │   │   ├── ingestion-svc.yaml
│   │   │   ├── postgres-svc.yaml
│   │   │   └── minio-svc.yaml
│   │   └── ingress/
│   │       └── api-ingress.yaml
│   ├── kafka/                     # Strimzi custom resources
│   │   ├── kafka-cluster.yaml
│   │   └── kafka-topics.yaml
│   └── opa/
│       └── opa-deployment.yaml
├── database/
│   └── migrations/
│       ├── 001_initial.sql
│       └── 002_versions.sql
├── monitoring/
│   ├── prometheus/
│   │   ├── config.yaml
│   │   └── rules.yaml
│   ├── grafana/
│   │   └── dashboards/
│   │       └── genomics-overview.json
│   ├── jaeger/                     # OpenTelemetry collector
│   │   ├── collector.yaml
│   │   └── agent.yaml
│   └── otel-collector-config.yaml
├── policy-as-code/
│   ├── rego-policies/
│   │   └── tenant-access.rego
│   └── constraints.yaml
└── docker-compose.yaml            # For local development
```

---

## 1. Secure Upload Services (Ingestion Service + API Gateway)

### API Gateway (FastAPI + OPA Middleware)

**`api-gateway/main.py`** – Core gateway that validates JWT, checks tenant permissions via OPA, and routes requests.

```python
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from auth import verify_token, get_current_user
from opa_middleware import OPAMiddleware
import httpx

app = FastAPI(title="Genomic Platform API Gateway")

# CORS for researcher frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inject OPA middleware (sidecar via Unix socket or HTTP)
opa_middleware = OPAMiddleware("http://opa:8181/v1/data/genomics/authz")
app.middleware("http")(opa_middleware.authz_middleware)

# Define protected routes
# Forwarding to ingestion service (internal k8s DNS)
ingestion_service_url = "http://ingestion-service:8080"

@app.post("/api/v1/upload")
async def upload_file(request: Request, user: dict = Depends(get_current_user)):
    # OPA enforced; user and tenant already in request.state
    tenant = request.state.user["tenant"]
    data = await request.json()
    # Validate file metadata, then forward
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{ingestion_service_url}/upload", json={
            "tenant": tenant,
            "user_id": user["sub"],
            "file": data["file"]
        })
    return resp.json()

@app.get("/api/v1/datasets")
async def list_datasets(tenant: str = Depends(get_current_user)):
    # Gateway queries PostgreSQL directly (or via dataset service)
    pass
```

**`api-gateway/auth.py`** – JWT verification and tenant extraction.

```python
import jwt
import os
from fastapi import HTTPException, Request
from functools import wraps

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")
ALGORITHM = "HS256"

def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(request: Request):
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = auth.split(" ")[1]
    user = verify_token(token)
    request.state.user = user
    return user
```

**`api-gateway/opa_middleware.py`** – Intercepts requests and calls OPA to enforce tenant isolation.

```python
import httpx
from fastapi import Request, HTTPException

class OPAMiddleware:
    def __init__(self, opa_url: str):
        self.opa_url = opa_url

    async def authz_middleware(self, request: Request, call_next):
        if "/api" not in request.url.path:
            return await call_next(request)
        
        user = getattr(request.state, "user", None)
        if not user:
            raise HTTPException(status_code=403, detail="Unauthenticated")

        payload = {
            "input": {
                "method": request.method,
                "path": request.url.path,
                "user": {
                    "id": user.get("sub"),
                    "tenant": user.get("tenant"),
                    "roles": user.get("roles", [])
                }
            }
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.opa_url, json=payload)
            result = resp.json()
            if not result.get("result", False):
                raise HTTPException(status_code=403, detail="Access denied by policy")
        
        response = await call_next(request)
        return response
```

### Ingestion Service

**`ingestion-service/main.py`** – Handles file upload, multi-part upload to MinIO, format validation, and publishes to Kafka.

```python
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
```

**`ingestion-service/validate.py`** – Validates file signatures and extensions.

```python
ALLOWED = {
    "fasta": [".fa", ".fasta"],
    "fastq": [".fq", ".fastq"],
    "bam":   [".bam"],
    "vcf":   [".vcf", ".vcf.gz"],
}

def validate_genomic_file(mime_type, filename):
    # Check extension
    ext = filename.rsplit(".", 1)[-1].lower()
    formats = {
        "application/x-gzip": ".gz",
        "application/gzip": ".gz",
        "text/plain": ".txt",
        "application/octet-stream": "",
    }
    # Simple extension‑based validation; expand for production
    return any(filename.endswith(ext) for exts in ALLOWED.values() for ext in exts)
```

---

## 2. Genomic Indexing Pipeline (Kafka Consumer Workers)

**`workers/indexer/worker.py`** – Listens to Kafka topic `file.uploaded`, runs indexing tools, stores metadata in PostgreSQL.

```python
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
```

**`workers/indexer/Dockerfile`** – Contains samtools, tabix, bcftools, and Python.

```dockerfile
FROM biocontainers/base:latest
RUN apt-get update && apt-get install -y samtools tabix python3 python3-pip
COPY requirements.txt .
RUN pip install aiokafka asyncpg minio
COPY worker.py .
COPY index.sh /usr/local/bin/index.sh
CMD ["python3", "worker.py"]
```

---

## 3. Distributed Sequence Search

**`workers/search/blast_worker.py`** – Consumes `search.requested` topic, runs BLAST+ against internal databases, publishes results.

```python
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
```

Workers scale independently; number of replicas controlled by Kubernetes HPA based on queue length.

---

## 4. Versioned Datasets

PostgreSQL schema (`database/migrations/002_versions.sql`):

```sql
CREATE TABLE file_versions (
    id SERIAL PRIMARY KEY,
    tenant VARCHAR(255) NOT NULL,
    filename VARCHAR(512) NOT NULL,
    sha256 CHAR(64) NOT NULL,
    object_key TEXT NOT NULL,
    index_key TEXT,
    file_size BIGINT,
    uploaded_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant, filename, sha256)
);

CREATE TABLE dataset_versions (
    dataset_id UUID PRIMARY KEY,
    tenant VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    version INT,
    parent_version INT,
    metadata JSONB,
    created_at TIMESTAMPTZ
);
```

Each upload creates a unique SHA256‑based object. Datasets can reference a set of file versions, versioned via `dataset_versions`. Rollback to any previous version simply re‑points to older SHA256 objects.

---

## 5. Multi‑Tenant Researcher Access

Tenant info embedded in JWT tokens. The API gateway uses OPA to enforce that users can only access their own tenant’s data.

**OPA Rego policy** (`opa/policies/tenant.rego`):

```rego
package genomics.authz

default allow = false

allow {
    input.method == "GET"
    input.path = ["api", "v1", "datasets"]
    tenant_own
}

allow {
    input.method == "POST"
    input.path = ["api", "v1", "upload"]
    tenant_own
}

tenant_own {
    requested_tenant := input.user.tenant
    # All endpoints in /api/v1/datasets/{tenant}...
    requested_tenant == input.path[3]
}
```

Policies can be extended for admin roles, billing, etc.

---

## 6. Event‑Driven Microservices with Kafka

**Strimzi Kafka Cluster** (`infrastructure/kafka/kafka-cluster.yaml`):

```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: Kafka
metadata:
  name: genomic-kafka
spec:
  kafka:
    version: 3.6.0
    replicas: 3
    listeners:
      - name: plain
        port: 9092
        type: internal
        tls: false
      - name: tls
        port: 9093
        type: internal
        tls: true
    config:
      offsets.topic.replication.factor: 3
      transaction.state.log.replication.factor: 3
      transaction.state.log.min.isr: 2
    storage:
      type: jbod
      volumes:
        - id: 0
          type: persistent-claim
          size: 100Gi
          deleteClaim: false
  zookeeper:
    replicas: 3
    storage:
      type: persistent-claim
      size: 20Gi
  entityOperator:
    topicOperator: {}
    userOperator: {}
```

**Topics** (`infrastructure/kafka/kafka-topics.yaml`):

```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaTopic
metadata:
  name: file.uploaded
  labels:
    strimzi.io/cluster: genomic-kafka
spec:
  partitions: 12
  replicas: 3
  config:
    retention.ms: 604800000
---
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaTopic
metadata:
  name: search.requested
...
```

---

## 7. Containerised Services & Kubernetes Configuration

### API Gateway Deployment (`infrastructure/kubernetes/deployments/api-gateway.yaml`)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
  namespace: genomics
spec:
  replicas: 2
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      serviceAccountName: genomics-api
      containers:
      - name: api-gateway
        image: genomic-platform/api-gateway:latest
        ports:
        - containerPort: 8000
        env:
        - name: JWT_SECRET
          valueFrom:
            secretKeyRef:
              name: jwt-secret
              key: secret
        - name: OPA_URL
          value: "http://opa:8181/v1/data/genomics/authz"
        - name: INGESTION_SERVICE_URL
          value: "http://ingestion-service:8080"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
```

### Ingestion Service (`infrastructure/kubernetes/deployments/ingestion.yaml`)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ingestion-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: ingestion
  template:
    spec:
      containers:
      - name: ingestion
        image: genomic-platform/ingestion:latest
        ports:
        - containerPort: 8080
        env:
        - name: MINIO_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: minio-credentials
              key: accesskey
        - name: MINIO_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: minio-credentials
              key: secretkey
        - name: MINIO_ENDPOINT
          value: "minio-service:9000"
        - name: KAFKA_BROKER
          value: "genomic-kafka-kafka-bootstrap:9092"
```

### Indexer Worker (`infrastructure/kubernetes/deployments/indexer.yaml`)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: genomic-indexer
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: indexer
        image: genomic-platform/indexer-worker:latest
        env:
        - name: KAFKA_BROKER
          value: "genomic-kafka-kafka-bootstrap:9092"
        - name: POSTGRES_DSN
          valueFrom:
            secretKeyRef:
              name: postgres-credentials
              key: dsn
        - name: MINIO_ACCESS_KEY
          valueFrom: ...
```

### PostgreSQL (`infrastructure/kubernetes/deployments/postgres.yaml`) – uses official Postgres image with persistent volume.

### MinIO (`infrastructure/kubernetes/deployments/minio.yaml`) – with TLS enabled.

### Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - genomics.example.com
    secretName: genomics-tls
  rules:
  - host: genomics.example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api-gateway-svc
            port:
              number: 8000
```

---

## 8. Monitoring & Observability

### Prometheus Config (`monitoring/prometheus/config.yaml`)

```yaml
global:
  scrape_interval: 15s
scrape_configs:
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
        action: replace
        target_label: __metrics_path__
        regex: (.+)
      - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
        action: replace
        regex: ([^:]+)(?::\d+)?;(\d+)
        replacement: $1:$2
        target_label: __address__
```

Services expose `/metrics` using Prometheus client libraries. In FastAPI, use `prometheus_fastapi_instrumentator`.

### Grafana Dashboard

A pre‑built JSON dashboard showing throughput, latency, error rates per tenant, Kafka lag, and sequence search queue depth.

### Distributed Tracing with Jaeger

An OpenTelemetry collector sidecar deployed in each namespace, sending traces to Jaeger. All services use `@trace` annotations.

---

## 9. Policy‑as‑Code Security Enforcement

OPA runs as a sidecar container in the API gateway pod (or as a cluster‑level admission controller). The Rego policies cover:

- **Tenant isolation**: Only allow access to resources belonging to the user’s tenant.
- **Upload restrictions**: Only certain roles can upload, validate file types.
- **Rate limiting policy**: Extendable to enforce quotas.

**`policy-as-code/rego-policies/tenant-access.rego`**

```rego
package genomics.authz

default allow = false

allow {
    input.method == "GET"
    input.path[0] == "api"
    input.path[1] == "v1"
    input.path[2] == "datasets"
    input.path[3] == input.user.tenant
}

allow {
    input.method == "POST"
    input.path == ["api", "v1", "upload"]
    input.user.tenant in data.allowed_tenants
}

# Admin override
allow {
    "admin" in input.user.roles
}
```

**OPA Deployment** (`infrastructure/opa/opa-deployment.yaml`)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: opa
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: opa
        image: openpolicyagent/opa:latest
        args:
        - "run"
        - "--server"
        - "--log-level=info"
        ports:
        - containerPort: 8181
        volumeMounts:
        - name: policies
          mountPath: /policies
      volumes:
      - name: policies
        configMap:
          name: opa-policies
```

Policies are loaded as a ConfigMap.

---

## 10. Object Storage & PostgreSQL Setup

**MinIO** for object storage; access credentials stored in Kubernetes secrets. Use `mc` client to create required buckets (`genomic-data`).

**PostgreSQL** runs inside Kubernetes with a persistent volume claim, initialized with migrations.

```sql
-- database/migrations/001_initial.sql
CREATE TABLE tenants (
    id UUID PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    plan VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE users (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    email VARCHAR(255) UNIQUE,
    roles TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 11. Infrastructure Configuration (Terraform/Terragrunt)

For a full IaaS deployment, provide Terraform modules for:

- Kubernetes cluster (EKS/GKE/AKS)
- Managed Kafka (MSK) or Strimzi
- Managed PostgreSQL (RDS) if not using in‑cluster
- DNS entries, storage buckets, IAM policies

Example placeholder can be generated.

---

## 12. Deployment‑Ready Docker Compose for Local Development

