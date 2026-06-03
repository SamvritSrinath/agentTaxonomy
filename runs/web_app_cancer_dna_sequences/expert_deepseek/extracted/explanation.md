# Scalable Genomic Data Management Platform for Cancer Bioinformatics

This blueprint delivers a production‑ready, event‑driven microservices architecture for ingesting, indexing, versioning, searching, and managing genomic data formats (FASTA, FASTQ, BAM, VCF). It supports multi‑tenancy, distributed sequence search, strong security, and full observability. All components are containerised and orchestrated by Kubernetes, with Kafka as the message backbone, PostgreSQL for metadata, and object storage (MinIO/S3) for raw files.

## Architecture Overview
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
---

## 1. Secure Upload Services (Ingestion Service + API Gateway)

### API Gateway (FastAPI + OPA Middleware)

**`api-gateway/main.py`** – Core gateway that validates JWT, checks tenant permissions via OPA, and routes requests.
**`api-gateway/auth.py`** – JWT verification and tenant extraction.
**`api-gateway/opa_middleware.py`** – Intercepts requests and calls OPA to enforce tenant isolation.
### Ingestion Service

**`ingestion-service/main.py`** – Handles file upload, multi-part upload to MinIO, format validation, and publishes to Kafka.
**`ingestion-service/validate.py`** – Validates file signatures and extensions.
---

## 2. Genomic Indexing Pipeline (Kafka Consumer Workers)

**`workers/indexer/worker.py`** – Listens to Kafka topic `file.uploaded`, runs indexing tools, stores metadata in PostgreSQL.
**`workers/indexer/Dockerfile`** – Contains samtools, tabix, bcftools, and Python.
---

## 3. Distributed Sequence Search

**`workers/search/blast_worker.py`** – Consumes `search.requested` topic, runs BLAST+ against internal databases, publishes results.
Workers scale independently; number of replicas controlled by Kubernetes HPA based on queue length.

---

## 4. Versioned Datasets

PostgreSQL schema (`database/migrations/002_versions.sql`):
Each upload creates a unique SHA256‑based object. Datasets can reference a set of file versions, versioned via `dataset_versions`. Rollback to any previous version simply re‑points to older SHA256 objects.

---

## 5. Multi‑Tenant Researcher Access

Tenant info embedded in JWT tokens. The API gateway uses OPA to enforce that users can only access their own tenant’s data.

**OPA Rego policy** (`opa/policies/tenant.rego`):
Policies can be extended for admin roles, billing, etc.

---

## 6. Event‑Driven Microservices with Kafka

**Strimzi Kafka Cluster** (`infrastructure/kafka/kafka-cluster.yaml`):
**Topics** (`infrastructure/kafka/kafka-topics.yaml`):
---

## 7. Containerised Services & Kubernetes Configuration

### API Gateway Deployment (`infrastructure/kubernetes/deployments/api-gateway.yaml`)
### Ingestion Service (`infrastructure/kubernetes/deployments/ingestion.yaml`)
### Indexer Worker (`infrastructure/kubernetes/deployments/indexer.yaml`)
### PostgreSQL (`infrastructure/kubernetes/deployments/postgres.yaml`) – uses official Postgres image with persistent volume.

### MinIO (`infrastructure/kubernetes/deployments/minio.yaml`) – with TLS enabled.

### Ingress
---

## 8. Monitoring & Observability

### Prometheus Config (`monitoring/prometheus/config.yaml`)
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
**OPA Deployment** (`infrastructure/opa/opa-deployment.yaml`)
Policies are loaded as a ConfigMap.

---

## 10. Object Storage & PostgreSQL Setup

**MinIO** for object storage; access credentials stored in Kubernetes secrets. Use `mc` client to create required buckets (`genomic-data`).

**PostgreSQL** runs inside Kubernetes with a persistent volume claim, initialized with migrations.
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
