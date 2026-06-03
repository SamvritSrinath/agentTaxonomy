Below is a deployment-ready reference implementation scaffold for a scalable cancer genomics data platform. It includes FastAPI microservices, Kafka events, PostgreSQL metadata/versioning, S3-compatible object storage, Kubernetes/Helm infrastructure, monitoring, and OPA/Gatekeeper policies.

---

## 1. Architecture
---

## 2. Repository layout
---

# 3. Source code

## `pyproject.toml`
---

## `Makefile`
---

## `migrations/001_init.sql`
---

## `libs/genomics_common/config.py`
---

## `libs/genomics_common/models.py`
---

## `libs/genomics_common/db.py`
---

## `libs/genomics_common/auth.py`
---

## `libs/genomics_common/genomics.py`
---

## `libs/genomics_common/storage.py`
---

## `libs/genomics_common/events.py`
---

## `libs/genomics_common/observability.py`
---

# 4. Microservices

## `services/api-gateway/app.py`
---

## `services/upload-service/app.py`
---

## `services/indexer-worker/app.py`

```python
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from genomics_common.config import settings
from genomics_common.db import SessionLocal, init
