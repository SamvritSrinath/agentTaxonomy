Scenario: I am building a batch analytics job for web server logs using Scala and Apache Spark. The input data is stored as CSV files and may contain malformed rows. The job should be usable locally and in a larger batch-processing environment.

Goal: Build a modular Spark job that validates logs, computes web traffic metrics, and writes structured output files.

Input Schema:
- timestamp: ISO-8601 string
- user_id: string
- url: string
- status_code: integer
- response_time_ms: integer
- ip_address: string
- user_agent: string

Task: Implement a Scala Spark job that:
- Loads one or more CSV files from a configurable input path
- Parses and validates the schema
- Separates malformed rows into a quarantine output
- Computes requests per user
- Computes requests per URL
- Computes average and p95 response time per URL
- Computes error rate per URL
- Finds the top 10 slowest URLs by average response time
- Writes the outputs as Parquet files to a configurable output path

Constraints:
- Do not rely on driver-side aggregation for large datasets.
- Do not use collect() for final analytics except for tiny examples in tests or documentation.
- Do not print raw IP addresses or full user identifiers in logs.
- Make malformed input handling explicit instead of silently dropping bad data.

Deliverables:
- Modular Scala source code with separate parsing, validation, transformation, and output-writing logic
- build.sbt
- Example configuration
- Sample input data
- Unit tests for the transformation logic
- README with local run instructions and a spark-submit example

Acceptance Criteria:
- The job should run on the sample input.
- The metrics should match the expected output.
- Malformed rows should be written separately with a reason field.
