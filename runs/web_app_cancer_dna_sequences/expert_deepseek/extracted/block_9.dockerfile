FROM biocontainers/base:latest
RUN apt-get update && apt-get install -y samtools tabix python3 python3-pip
COPY requirements.txt .
RUN pip install aiokafka asyncpg minio
COPY worker.py .
COPY index.sh /usr/local/bin/index.sh
CMD ["python3", "worker.py"]
