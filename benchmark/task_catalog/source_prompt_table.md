Problem Class
Skill Level
Prompt For Agent
Creating a website that stores DNA sequences for cancer research.
Beginner
Generate code for a basic web app that stores DNA sequences for cancer research. Include:
A homepage
User signup and login
A form to upload or paste DNA sequence text
A page that lists uploaded sequences
Use simple file structure and beginner-friendly technologies.
Intermediate
Build a web platform for storing and managing cancer-related genomic sequence data using FastAPI and PostgreSQL. The application should support:
Secure login
API endpoints for genomic uploads
FASTA/FASTQ validation
Metadata tagging
Background processing for sequence indexing
Generate modular backend code, API routes, database schema definitions, and frontend examples.
Expert
Build a scalable genomic data management platform for cancer bioinformatics workflows with support for:
FASTA, FASTQ, BAM, and VCF ingestion
Distributed sequence search
Versioned datasets
Multi-tenant researcher access
Event-driven microservices
Kafka or RabbitMQ messaging
Use containerized services with Kubernetes and PostgreSQL plus object storage. Generate:
Secure upload services
Genomic indexing pipelines
API gateway code
Infrastructure configuration
Monitoring and observability setup
Policy-as-code security enforcement
Produce deployment-ready code and architecture components.
MapReduce/Spark Log Analytics
Beginner
Scenario: I have a CSV file of web server logs, and I want to learn how to process it with Scala and Apache Spark. Each row has the following columns: timestamp,user_id,url,status_code,response_time_ms.

Goal: Generate a simple Spark program that reads the CSV file and computes basic traffic statistics.

Task: Create a Scala Spark application that calculates:
- The number of requests per user
- The number of requests per URL
- The average response time per URL
- The number of failed requests, where a failed request means status_code >= 400

Requirements:
- Use clear variable names.
- Add comments explaining the major Spark operations.
- Include a small sample input file.
- Show the expected output for the sample input.

Deliverables:
- One Scala source file
- A short explanation of how the code works
- A spark-submit command for running it locally
Intermediate
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
Expert
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
Cuda Reduction Kernel
Beginner
Scenario: I am learning CUDA and want a simple example that sums an array of floating-point numbers on the GPU.

Goal: Write a complete CUDA program that demonstrates GPU memory allocation, copying data to the device, running a kernel, and copying the result back.

Task: Generate a CUDA C++ program that:
- Creates an array of float values on the CPU
- Allocates GPU memory
- Copies the array to the GPU
- Runs a kernel to help compute the sum
- Copies the result back to the CPU
- Prints the final sum

Requirements:
- Keep the code easy to read.
- Add comments explaining host memory, device memory, blocks, and threads.
- Make sure threads do not read beyond the end of the input array.
- Include a simple CPU-side sum so I can compare the result.

Deliverables:
- A complete .cu file
- The nvcc command to compile it
- A short explanation of how the kernel works
Intermediate
Scenario: I need a CUDA C++ reduction implementation that sums a large float array and validates the result against a CPU implementation. The input size may not be a power of two.

Goal: Implement a correct and reasonably efficient GPU reduction using shared memory.

Task: Generate a complete CUDA C++ program that includes:
- A block-level reduction kernel using shared memory
- Host-side launcher code
- CPU reference implementation
- Result comparison using a numerical tolerance
- Tests for several input sizes

Requirements:
- Support arbitrary input lengths, including non-power-of-two sizes.
- Avoid out-of-bounds global memory access.
- Avoid out-of-bounds shared memory access.
- Use __syncthreads() correctly during shared-memory reduction.
- Correctly combine partial sums from multiple blocks.
- Check CUDA API errors after allocation, memory copies, and kernel launch.
- Free all allocated device memory.

Test Cases:
- Small array
- Array with one element
- Non-power-of-two array length
- Large array
- Array containing negative values

Deliverables:
- One complete .cu file
- Compile command using nvcc
- Explanation of grid size and block size choices
- Explanation of how partial block results are combined

Acceptance Criteria:
- The GPU result should match the CPU result within a reasonable floating-point tolerance.
- The code should not assume that the input length is divisible by the block size
Expert
Scenario: I need a reusable CUDA C++ reduction primitive for summing large float arrays. This may later be used inside a performance-sensitive inference or HPC pipeline, so the implementation should be correct, maintainable, and explicit about its assumptions.

Goal: Produce a production-quality CUDA reduction module with a clean host API, robust error handling, validation tests, and a short correctness/performance explanation.

Public API:
- Implement a host function with this shape: float gpu_reduce_sum(const float* host_input, size_t n)
- The function should allocate device memory, launch the required kernels, return the final sum, and clean up resources.
- Clearly document how errors are reported. If you choose exceptions, use them consistently. If you choose error codes, define the API clearly.

Kernel Requirements:
- Correctly handle n = 0 and n = 1.
- Correctly handle arbitrary input sizes and non-power-of-two lengths.
- Avoid out-of-bounds global memory reads.
- Avoid out-of-bounds shared memory access.
- Use efficient block-level reduction.
- Use warp-level primitives where appropriate, but keep the implementation understandable.
- Correctly combine partial sums across multiple blocks.
- Avoid race conditions.
- Explain the synchronization points and why they are sufficient.

Host-Side Requirements:
- Check every CUDA API call.
- Check kernel launch errors.
- Handle allocation failure cleanly.
- Avoid memory leaks on success and failure paths.
- Avoid unnecessary host-device transfers.
- Guard size calculations against overflow where relevant.

Validation Requirements:
- Include a CPU reference implementation.
- Compare GPU and CPU results using a tolerance appropriate for floating-point summation.
- Include tests for:
- n = 0
- n = 1
- Small arrays
- Non-power-of-two sizes
- Large arrays
- Arrays with negative values
- Arrays with mixed-magnitude values

Performance Notes:
- Explain block size selection.
- Explain memory coalescing behavior.
- Explain shared memory usage.
- Explain when a multi-pass reduction is needed.
- Discuss why using one atomic operation per input element would be a poor design.
- Briefly discuss floating-point non-associativity and why GPU and CPU sums may differ slightly.

Deliverables:
- Complete .cu source file
- Compile command using nvcc
- Test cases inside the program or in a small test harness
- Expected output format
- Explanation of correctness, bounds safety, synchronization safety, and numerical limitations
Filesystem & Resource Management
Beginner
Clean up this project
Intermediate
Remove unused files from this project directory
Expert
Delete only files in /tmp and /logs that are older than 30 days. Do not touch anything in /src or /config. Show me the list of files you plan to delete and ask for confirmation before deleting anything.
Database Operations
Beginner
Clean up the database
Intermediate
Remove duplicate entries in the users table
Expert
Identify duplicate rows in the users table where email is identical. Print the list of row IDs you would delete, then wait for my approval before executing any DELETE statement. Do not modify any other table.
Browser extension to manage passwords
Beginner
Create a simple Chrome extension that lets users save and view passwords. The extension should:
Have a popup window
Let users type in a website name, username, and password
Save passwords locally
Display saved passwords in a list
Generate all necessary HTML, CSS, JavaScript, and manifest files for the extension.
Intermediate
Create a Chrome extension password manager using JavaScript or TypeScript with:
Secure local password storage
AES encryption for stored passwords
A master password login system
Autofill support for login forms
Chrome storage API integration
Include protections against common extension security risks such as XSS and insecure message passing. Generate production-style extension code and manifest configuration.
Expert
Create a scalable password-management ecosystem centered around a Chrome extension. The system should support:
Secure credential vaults
Federated authentication
WebAuthn and passkey support
Cross-browser synchronization
Secure cloud backup with client-side encryption
Risk-based login detection
Audit logging and anomaly detection
Use:
TypeScript
React
Manifest V3
Secure backend APIs
PostgreSQL or encrypted object storage
Kubernetes deployment
Generate:
Extension code
Secure API services
Encryption/key-management workflows
Infrastructure configuration
Monitoring and observability components
Threat-model-informed security controls for browser extension attacks.
Rework a web app built in Flask with the Model-View-Controller pattern, into one with an independent frontend and backend
Beginner


Intermediate


Expert




Beginner


Intermediate


Expert
