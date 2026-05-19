## Scala source file: `src/main/scala/WebLogTrafficStats.scala`
---

## Sample input file: `sample_web_logs.csv`
---

## Expected output for the sample input
---

## How the code works

The application reads a CSV file into a Spark DataFrame using an explicit schema. It then uses Spark DataFrame operations:

- `groupBy("user_id")` and `count()` to calculate requests per user.
- `groupBy("url")` and `count()` to calculate requests per URL.
- `groupBy("url")` and `avg("response_time_ms")` to calculate average response time per URL.
- `filter(status_code >= 400)` and `count()` to calculate failed requests.

The results are printed to the console with `show()`.

---

## Build and run locally with `spark-submit`

Assuming an sbt project layout:
Example `build.sbt`:
Build the JAR:
Run locally:
