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
