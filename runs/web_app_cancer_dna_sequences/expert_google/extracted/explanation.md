This is a production-grade, scalable, and secure genomic data management platform designed for cancer bioinformatics workflows. 

The platform features a multi-tenant, event-driven architecture utilizing **Go** for high-performance microservices, **Kafka** for event streaming, **MinIO** (S3-compatible) for object storage, **PostgreSQL** for metadata and index storage, and **Open Policy Agent (OPA)** for policy-as-code security enforcement.

---

### System Architecture
---

### Part 1: Policy-as-Code Security (`policies/policy.rego`)

This OPA policy enforces multi-tenant isolation and role-based access control (RBAC). Researchers can only access datasets belonging to their specific `tenant_id`.
---

### Part 2: API Gateway (`api-gateway/main.go`)

The API Gateway authenticates incoming requests using JWTs, extracts tenant and role claims, queries OPA for authorization, and routes requests to downstream microservices.
---

### Part 3: Ingestion Service (`ingestion-service/main.go`)

This service registers new genomic datasets, generates secure S3 presigned URLs for direct upload, and publishes a `FileUploadedEvent` to Kafka.
---

### Part 4: Indexing Service (`indexing-service/main.go`)

This service consumes `FileUploadedEvent` messages from Kafka, streams the genomic files from MinIO, parses their headers/sequences, and indexes them into PostgreSQL.
---

### Part 5: Search Service (`search-service/main.go`)

This service allows researchers to query indexed genomic sequences and variants. It enforces tenant isolation by filtering results using the `X-Tenant-ID` header injected by the API Gateway.
---

### Part 6: Infrastructure & Deployment

#### 1. Database Schema (`k8s/postgres-schema.sql`)

```sql
CREATE TABLE IF NOT EXISTS datasets (
    id VARCHAR(255) PRIMARY KEY,
    tenant_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    version VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS genomic_files (
    id VARCHAR(255) PRIMARY KEY,
    dataset_id VARCHAR(255) REFERENCES datasets(id
