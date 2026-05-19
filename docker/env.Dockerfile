ARG BASE_IMAGE=unsafe-autonomy-bench-base:latest
FROM ${BASE_IMAGE}

ARG REPO_NAME=placeholder/repo
ARG BASE_COMMIT=0000000000000000000000000000000000000000

RUN mkdir -p /workspace/repo /workspace/runtime /workspace/logs

WORKDIR /workspace/repo

# A real benchmark runner would clone the target repo and checkout BASE_COMMIT
# during image construction or container start. This scaffold keeps the layer
# contract explicit without requiring network access at build time.
RUN printf "repo=%s\ncommit=%s\n" "$REPO_NAME" "$BASE_COMMIT" > /workspace/runtime/seed-metadata.txt
