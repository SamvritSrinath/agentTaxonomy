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
