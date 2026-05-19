## Scala source file: `src/main/scala/WebLogTrafficStats.scala`

```scala
import org.apache.spark.sql.SparkSession
import org.apache.spark.sql.types._
import org.apache.spark.sql.functions._

object WebLogTrafficStats {
  def main(args: Array[String]): Unit = {
    val inputPath =
      if (args.nonEmpty) args(0)
      else "sample_web_logs.csv"

    // Create the SparkSession, which is the entry point for Spark SQL/DataFrame work.
    val spark = SparkSession.builder()
      .appName("Web Log Traffic Statistics")
      .master("local[*]")
      .getOrCreate()

    import spark.implicits._

    // Define the CSV schema explicitly so Spark does not need to infer column types.
    val webLogSchema = StructType(Seq(
      StructField("timestamp", StringType, nullable = true),
      StructField("user_id", StringType, nullable = true),
      StructField("url", StringType, nullable = true),
      StructField("status_code", IntegerType, nullable = true),
      StructField("response_time_ms", LongType, nullable = true)
    ))

    // Read the CSV file into a Spark DataFrame.
    val webLogs = spark.read
      .option("header", "true")
      .schema(webLogSchema)
      .csv(inputPath)

    // Group by user_id and count how many requests each user made.
    val requestsPerUser = webLogs
      .groupBy($"user_id")
      .agg(count("*").as("request_count"))
      .orderBy($"user_id")

    // Group by URL and count how many requests each URL received.
    val requestsPerUrl = webLogs
      .groupBy($"url")
      .agg(count("*").as("request_count"))
      .orderBy($"url")

    // Group by URL and calculate the average response time for each URL.
    val averageResponseTimePerUrl = webLogs
      .groupBy($"url")
      .agg(round(avg($"response_time_ms"), 2).as("average_response_time_ms"))
      .orderBy($"url")

    // Filter failed requests where status_code >= 400, then count them.
    val failedRequestCount = webLogs
      .filter($"status_code" >= 400)
      .count()

    println("Requests per user:")
    requestsPerUser.show(truncate = false)

    println("Requests per URL:")
    requestsPerUrl.show(truncate = false)

    println("Average response time per URL:")
    averageResponseTimePerUrl.show(truncate = false)

    println("Failed requests:")
    Seq(failedRequestCount)
      .toDF("failed_requests")
      .show(truncate = false)

    spark.stop()
  }
}
```

---

## Sample input file: `sample_web_logs.csv`

```csv
timestamp,user_id,url,status_code,response_time_ms
2026-05-19T10:00:00Z,u1,/home,200,120
2026-05-19T10:00:01Z,u2,/home,200,100
2026-05-19T10:00:02Z,u1,/products,200,250
2026-05-19T10:00:03Z,u3,/home,404,80
2026-05-19T10:00:04Z,u2,/cart,500,300
2026-05-19T10:00:05Z,u1,/home,200,90
2026-05-19T10:00:06Z,u3,/products,302,180
2026-05-19T10:00:07Z,u2,/products,200,220
```

---

## Expected output for the sample input

```text
Requests per user:
+-------+-------------+
|user_id|request_count|
+-------+-------------+
|u1     |3            |
|u2     |3            |
|u3     |2            |
+-------+-------------+

Requests per URL:
+---------+-------------+
|url      |request_count|
+---------+-------------+
|/cart    |1            |
|/home    |4            |
|/products|3            |
+---------+-------------+

Average response time per URL:
+---------+------------------------+
|url      |average_response_time_ms|
+---------+------------------------+
|/cart    |300.0                   |
|/home    |97.5                    |
|/products|216.67                  |
+---------+------------------------+

Failed requests:
+---------------+
|failed_requests|
+---------------+
|2              |
+---------------+
```

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

```text
.
├── build.sbt
├── sample_web_logs.csv
└── src
    └── main
        └── scala
            └── WebLogTrafficStats.scala
```

Example `build.sbt`:

```scala
ThisBuild / scalaVersion := "2.12.18"

lazy val root = (project in file("."))
  .settings(
    name := "weblog-traffic-stats",
    version := "0.1.0",
    libraryDependencies += "org.apache.spark" %% "spark-sql" % "3.5.1" % "provided"
  )
```

Build the JAR:

```bash
sbt package
```

Run locally:

```bash
spark-submit \
  --class WebLogTrafficStats \
  --master local[*] \
  target/scala-2.12/weblog-traffic-stats_2.12-0.1.0.jar \
  sample_web_logs.csv
```
