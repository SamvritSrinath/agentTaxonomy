## 1. Scala source file: `WebLogTrafficStats.scala`

```scala
import org.apache.spark.sql.SparkSession
import org.apache.spark.sql.functions._
import org.apache.spark.sql.types._

object WebLogTrafficStats {
  def main(args: Array[String]): Unit = {
    if (args.length != 1) {
      System.err.println("Usage: WebLogTrafficStats <input_csv_path>")
      System.exit(1)
    }

    val inputCsvPath = args(0)

    val spark = SparkSession.builder()
      .appName("Web Log Traffic Statistics")
      .getOrCreate()

    import spark.implicits._

    // Define the CSV schema explicitly instead of relying on schema inference.
    val webLogSchema = StructType(Seq(
      StructField("timestamp", StringType, nullable = true),
      StructField("user_id", StringType, nullable = true),
      StructField("url", StringType, nullable = true),
      StructField("status_code", IntegerType, nullable = true),
      StructField("response_time_ms", DoubleType, nullable = true)
    ))

    // Read the CSV file into a Spark DataFrame.
    val webLogs = spark.read
      .option("header", "true")
      .schema(webLogSchema)
      .csv(inputCsvPath)

    // Cache the DataFrame because it is reused by multiple aggregations.
    webLogs.cache()

    // Group requests by user_id and count how many requests each user made.
    val requestsPerUser = webLogs
      .groupBy($"user_id")
      .count()
      .withColumnRenamed("count", "request_count")
      .orderBy($"user_id")

    // Group requests by URL and count how many requests each URL received.
    val requestsPerUrl = webLogs
      .groupBy($"url")
      .count()
      .withColumnRenamed("count", "request_count")
      .orderBy($"url")

    // Group requests by URL and calculate the average response time for each URL.
    val averageResponseTimePerUrl = webLogs
      .groupBy($"url")
      .agg(round(avg($"response_time_ms"), 2).alias("average_response_time_ms"))
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

    println(s"Failed requests where status_code >= 400: $failedRequestCount")

    spark.stop()
  }
}
```

---

## 2. Sample input file: `sample_logs.csv`

```csv
timestamp,user_id,url,status_code,response_time_ms
2026-01-01T10:00:00Z,u1,/home,200,120
2026-01-01T10:00:01Z,u2,/home,200,80
2026-01-01T10:00:02Z,u1,/products,404,150
2026-01-01T10:00:03Z,u3,/checkout,500,300
2026-01-01T10:00:04Z,u2,/products,200,110
2026-01-01T10:00:05Z,u1,/home,302,100
2026-01-01T10:00:06Z,u3,/products,403,130
2026-01-01T10:00:07Z,u2,/checkout,200,250
```

---

## 3. Expected output for the sample input

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
|/checkout|2            |
|/home    |3            |
|/products|3            |
+---------+-------------+

Average response time per URL:
+---------+------------------------+
|url      |average_response_time_ms|
+---------+------------------------+
|/checkout|275.0                   |
|/home    |100.0                   |
|/products|130.0                   |
+---------+------------------------+

Failed requests where status_code >= 400: 3
```

---

## 4. How the code works

The program reads a CSV file into a Spark DataFrame using an explicit schema. It then performs four basic Spark operations:

1. `groupBy("user_id").count()` counts requests per user.
2. `groupBy("url").count()` counts requests per URL.
3. `groupBy("url").agg(avg("response_time_ms"))` calculates average response time per URL.
4. `filter(status_code >= 400).count()` counts failed requests.

The results are printed to the console using Spark’s `show()` method.

---

## 5. Build and run locally with `spark-submit`

Example `build.sbt` for packaging:

```scala
name := "web-log-traffic-stats"

version := "0.1.0"

scalaVersion := "2.12.18"

libraryDependencies += "org.apache.spark" %% "spark-sql" % "3.5.1" % "provided"
```

Directory layout:

```text
web-log-traffic-stats/
  build.sbt
  sample_logs.csv
  src/
    main/
      scala/
        WebLogTrafficStats.scala
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
  target/scala-2.12/web-log-traffic-stats_2.12-0.1.0.jar \
  sample_logs.csv
```
