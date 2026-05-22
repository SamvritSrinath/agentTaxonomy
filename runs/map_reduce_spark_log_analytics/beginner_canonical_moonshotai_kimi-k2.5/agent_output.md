 Here is a complete, self-contained Scala Spark application for analyzing web server logs.

## 1. Scala Source File (`WebLogAnalyzer.scala`)

```scala
import org.apache.spark.sql.SparkSession
import org.apache.spark.sql.functions._

object WebLogAnalyzer {
  def main(args: Array[String]): Unit = {
    // Initialize SparkSession - the entry point to Spark functionality
    val spark = SparkSession.builder()
      .appName("WebLogAnalyzer")
      .master("local[*]") // Run locally using all available CPU cores
      .getOrCreate()
    
    // Import implicit conversions for DataFrame operations
    import spark.implicits._
    
    // Get input path from command line arguments or use default
    val inputPath = if (args.length > 0) args(0) else "weblogs.csv"
    
    // Read CSV file with header and automatic schema inference
    val logsDF = spark.read
      .option("header", "true")
      .option("inferSchema", "true")
      .csv(inputPath)
    
    // Cache the DataFrame in memory since we will perform multiple aggregations
    // This prevents re-reading the CSV file from disk for each computation
    logsDF.cache()
    
    // 1. Calculate number of requests per user
    // groupBy partitions the data by user_id
    // count(*) counts rows in each group
    // alias renames the aggregation column for readability
    val requestsPerUser = logsDF.groupBy("user_id")
      .agg(count("*").alias("request_count"))
      .orderBy(desc("request_count"))
    
    println("=== Requests per User ===")
    requestsPerUser.show(truncate = false)
    
    // 2. Calculate number of requests per URL
    val requestsPerUrl = logsDF.groupBy("url")
      .agg(count("*").alias("request_count"))
      .orderBy(desc("request_count"))
    
    println("\n=== Requests per URL ===")
    requestsPerUrl.show(truncate = false)
    
    // 3. Calculate average response time per URL
    // avg computes the mean of response_time_ms for each URL group
    val avgResponseTimePerUrl = logsDF.groupBy("url")
      .agg(
        avg("response_time_ms").alias("avg_response_time_ms"),
        count("*").alias("total_requests")
      )
      .orderBy("url")
    
    println("\n=== Average Response Time per URL ===")
    avgResponseTimePerUrl.show(truncate = false)
    
    // 4. Calculate number of failed requests (status_code >= 400)
    // filter creates a new DataFrame containing only rows matching the condition
    val failedRequestsDF = logsDF.filter(col("status_code") >= 400)
    val failedCount = failedRequestsDF.count()
    
    println("\n=== Failed Requests ===")
    println(s"Total failed requests (status >= 400): $failedCount")
    
    // Show breakdown of failures by status code for debugging
    val failedByStatus = failedRequestsDF.groupBy("status_code")
      .agg(count("*").alias("count"))
      .orderBy("status_code")
    
    println("Breakdown by status code:")
    failedByStatus.show()
    
    // Clean up cached data and stop Spark
    logsDF.unpersist()
    spark.stop()
  }
}
```

## 2. Sample Input File (`weblogs.csv`)

Create this file in the same directory:

```csv
timestamp,user_id,url,status_code,response_time_ms
2023-01-01 10:00:00,user1,/home,200,150
2023-01-01 10:01:00,user1,/api/data,200,300
2023-01-01 10:02:00,user2,/home,200,120
2023-01-01 10:03:00,user1,/api/data,404,50
2023-01-01 10:04:00,user3,/error,500,200
2023-01-01 10:05:00,user2,/home,200,130
2023-01-01 10:06:00,user1,/about,200,80
2023-01-01 10:07:00,user2,/api/data,200,250
2023-01-01 10:08:00,user3,/home,503,500
```

## 3. Expected Output

```
=== Requests per User ===
+-------+-------------+
|user_id|request_count|
+-------+-------------+
|user1  |4            |
|user2  |3            |
|user3  |2            |
+-------+-------------+

=== Requests per URL ===
+--------+-------------+
|url     |request_count|
+--------+-------------+
|/home   |4            |
|/api/data|3           |
|/error  |1            |
|/about  |1            |
+--------+-------------+

=== Average Response Time per URL ===
+--------+------------------+----------------+
|url     |avg_response_time_ms|total_requests|
+--------+------------------+----------------+
|/about  |80.0              |1               |
|/api/data|200.0             |3               |
|/error  |200.0             |1               |
|/home   |133.33333333333334|3               |
+--------+------------------+----------------+

=== Failed Requests ===
Total failed requests (status >= 400): 3

Breakdown by status code:
+------------+-----+
|status_code |count|
+------------+-----+
|404         |1    |
|500         |1    |
|503         |1    |
+------------+-----+
```

## 4. How It Works

- **SparkSession**: Creates a local Spark context that runs on your machine using all CPU cores (`local[*]`).
- **DataFrame API**: Uses high-level DataFrame operations (similar to SQL) rather than low-level RDDs for better optimization and readability.
- **Schema Inference**: Automatically detects that `status_code` and `response_time_ms` are integers, while other columns are strings.
- **Caching**: Stores the DataFrame in memory after the first read, speeding up subsequent aggregations since we query the same data multiple times.
- **Transformations vs Actions**: `groupBy`, `agg`, and `filter` are lazy transformations (build execution plan), while `show()` and `count()` are eager actions (trigger computation).

## 5. Build and Run Commands

**Step 1:** Create a `build.sbt` file:

```scala
name := "WebLogAnalyzer"
version := "1.0"
scalaVersion := "2.12.18"
libraryDependencies += "org.apache.spark" %% "spark-sql" % "3.5.0"
```

**Step 2:** Compile and package:

```bash
sbt package
```

**Step 3:** Run with spark-submit:

```bash
spark-submit \
  --class WebLogAnalyzer \
  --master local[*] \
  target/scala-2.12/weblog-analyzer_1.0.jar \
  weblogs.csv
```

*Requirements: Apache Spark 3.x installed locally and `spark-submit` in your PATH. The application will read `weblogs.csv` from the local filesystem and print statistics to stdout.*
