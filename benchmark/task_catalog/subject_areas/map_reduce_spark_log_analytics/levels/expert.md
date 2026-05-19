Scenario: I am designing a production-oriented daily web traffic analytics pipeline using Scala and Apache Spark. The pipeline processes logs from local paths or object-storage-style paths and produces partitioned analytics datasets for downstream reporting. The data may be large, partially malformed, duplicated, or skewed.

Goal: Treat this as a small PRD and generate the code and supporting artifacts for a robust Spark batch pipeline.

Input Schema:
- timestamp: ISO-8601 string
- user_id: string
- url: string
- status_code: integer
- response_time_ms: integer
- ip_address: string
- user_agent: string
- request_id: string

Functional Requirements:
- Read one or more input paths from configuration.
- Support local filesystem paths and object-storage-style paths.
- Enforce schema validation before computing metrics.
- Quarantine malformed rows with structured reason codes.
- Deduplicate records by request_id.
- Normalize timestamps and derive a processing date.
- Write Parquet outputs partitioned by date.
- Produce separate output datasets for clean records, quarantined records, and aggregate metrics.

Analytics Requirements:
- Requests per user per day
- Requests per URL per day
- Average, p95, and p99 response time per URL per day
- Error rate per URL per day
- Daily active users
- Top slow endpoints per day
- Count of malformed records by reason code

Engineering Constraints:
- Avoid collect(), toPandas(), or driver-side aggregation for production-sized data.
- Use distributed aggregation patterns.
- Use approximate quantile logic appropriate for Spark-scale data.
- Explain where shuffles occur and why.
- Explain possible data-skew risks and how the implementation mitigates them.
- Validate output paths to avoid accidental writes outside the configured destination.
- Avoid logging raw IP addresses, raw user identifiers, or full malformed records.

Configuration Requirements:
- Input path
- Output path
- Quarantine path
- Processing date
- Application name
- Optional repartition count

Deliverables:
- Scala source code organized into clear modules
- build.sbt
- Configuration model and example config file
- Sample input dataset
- Expected output examples
- Unit tests for parsing, validation, deduplication, and aggregation
- README with local and cluster-style run commands
- Notes explaining partitioning, quantile computation, failure handling, and operational assumptions

Acceptance Criteria:
- The sample dataset should produce deterministic expected outputs.
- Malformed records should not corrupt aggregate metrics.
- Duplicate request_id values should be handled consistently.
- The implementation should be understandable enough for another engineer to extend.
