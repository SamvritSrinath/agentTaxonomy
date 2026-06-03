import os


class Settings:
    service_name = os.getenv("SERVICE_NAME", "genomics-service")

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://genomics:genomics@postgresql:5432/genomics",
    )

    kafka_bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    kafka_ingest_topic = os.getenv("KAFKA_INGEST_TOPIC", "genomics.ingest.requested")
    kafka_indexed_topic = os.getenv("KAFKA_INDEXED_TOPIC", "genomics.ingest.indexed")
    kafka_search_topic = os.getenv("KAFKA_SEARCH_TOPIC", "genomics.search.jobs")

    s3_endpoint_url = os.getenv("S3_ENDPOINT_URL", "http://minio:9000")
    s3_access_key = os.getenv("S3_ACCESS_KEY", "minioadmin")
    s3_secret_key = os.getenv("S3_SECRET_KEY", "minioadmin")
    s3_bucket = os.getenv("S3_BUCKET", "genomics")

    jwt_secret = os.getenv("JWT_SECRET", "change-me")
    jwt_issuer = os.getenv("JWT_ISSUER", "genomics-platform")
    jwt_audience = os.getenv("JWT_AUDIENCE", "genomics-api")

    upload_max_bytes = int(os.getenv("UPLOAD_MAX_BYTES", str(50 * 1024 * 1024 * 1024)))

    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")


settings = Settings()
