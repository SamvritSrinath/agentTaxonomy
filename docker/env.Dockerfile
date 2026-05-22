FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates git jq \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /workspace

ARG REPO_NAME=placeholder/repo
ARG BASE_COMMIT=0000000000000000000000000000000000000000

RUN mkdir -p /workspace/repo /workspace/runtime /workspace/logs

WORKDIR /workspace/repo

# A real benchmark runner would clone the target repo and checkout BASE_COMMIT
# during image construction or container start. This scaffold keeps the layer
# contract explicit without requiring network access at build time.
RUN printf "repo=%s\ncommit=%s\n" "$REPO_NAME" "$BASE_COMMIT" > /workspace/runtime/seed-metadata.txt
