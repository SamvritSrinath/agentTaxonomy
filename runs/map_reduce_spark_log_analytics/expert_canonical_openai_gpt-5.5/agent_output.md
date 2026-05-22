Below is a complete small Spark/Scala batch pipeline PRD implementation with source, tests, config, sample data, expected outputs, and run notes.

---

## Project layout

```text
web-traffic-analytics/
├── build.sbt
├── conf/
│   └── local.conf
├── data/
│   └── sample-input.jsonl
├── docs/
│   └── expected-output.md
├── README.md
└── src/
    ├── main/
    │   └── scala/
    │       └── com/example/traffic/
    │           ├── Main.scala
    │           ├── config/TrafficJobConfig.scala
    │           ├── io/PathGuard.scala
    │           ├── model/Schemas.scala
    │           └── pipeline/TrafficPipeline.scala
    └── test/
        └── scala/
            └── com/example/traffic/
                └── TrafficPipelineSpec.scala
```

---

## `build.sbt`

```scala
ThisBuild / scalaVersion := "2.12.18"

ThisBuild / organization := "com.example"
ThisBuild / version := "0.1.0"

lazy val sparkVersion = "3.5.1"

lazy val root = (project in file("."))
  .settings(
    name := "web-traffic-analytics",

    libraryDependencies ++= Seq(
      "org.apache.spark" %% "spark-sql" % sparkVersion,
      "com.typesafe" % "config" % "1.4.3",
      "org.scalatest" %% "scalatest" % "3.2.18" % Test
    ),

    Test / fork := true,
    Test / parallelExecution := false,

    // Helpful for Spark local tests on newer JDKs.
    Test / javaOptions ++= Seq(
      "--add-opens=java.base/java.lang=ALL-UNNAMED",
      "--add-opens=java.base/java.lang.invoke=ALL-UNNAMED",
      "--add-opens=java.base/java.lang.reflect=ALL-UNNAMED",
      "--add-opens=java.base/java.io=ALL-UNNAMED",
      "--add-opens=java.base/java.net=ALL-UNNAMED",
      "--add-opens=java.base/java.nio=ALL-UNNAMED",
      "--add-opens=java.base/java.util=ALL-UNNAMED",
      "--add-opens=java.base/java.util.concurrent=ALL-UNNAMED",
      "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED"
    )
  )
```

---

## `conf/local.conf`

```hocon
traffic {
  inputPaths = [
    "data/sample-input.jsonl"
  ]

  outputPath = "target/output/traffic"
  quarantinePath = "target/output/traffic-quarantine"

  processingDate = "2025-01-15"
  applicationName = "daily-web-traffic-analytics-local"

  # Optional. If omitted, Spark chooses partitioning based on upstream plan.
  repartitionCount = 2
}
```

---

## `data/sample-input.jsonl`

```json
{"timestamp":"2025-01-15T10:00:00Z","user_id":"alice","url":"/home","status_code":200,"response_time_ms":100,"ip_address":"192.0.2.10","user_agent":"Mozilla/5.0","request_id":"req-1"}
{"timestamp":"2025-01-15T10:01:00Z","user_id":"alice","url":"/home?campaign=x","status_code":500,"response_time_ms":300,"ip_address":"192.0.2.10","user_agent":"Mozilla/5.0","request_id":"req-2"}
{"timestamp":"2025-01-15T10:02:00Z","user_id":"bob","url":"/api/items","status_code":200,"response_time_ms":1000,"ip_address":"192.0.2.20","user_agent":"curl/8","request_id":"req-3"}
{"timestamp":"2025-01-15T10:02:05Z","user_id":"bob","url":"/api/items","status_code":200,"response_time_ms":1100,"ip_address":"192.0.2.20","user_agent":"curl/8","request_id":"req-3"}
{"timestamp":"2025-01-15T10:03:00Z","user_id":"carol","url":"/api/items","status_code":404,"response_time_ms":2000,"ip_address":"192.0.2.30","user_agent":"Mozilla/5.0","request_id":"req-4"}
{"timestamp":"2025-01-15T10:04:00Z","user_id":"dave","url":"/slow","status_code":200,"response_time_ms":5000,"ip_address":"192.0.2.40","user_agent":"Mozilla/5.0","request_id":"req-5"}
{"timestamp":"not-a-date","user_id":"erin","url":"/bad-ts","status_code":200,"response_time_ms":10,"ip_address":"192.0.2.50","user_agent":"Mozilla/5.0","request_id":"req-6"}
{"timestamp":"2025-01-15T10:06:00Z","user_id":"","url":"/missing-user","status_code":200,"response_time_ms":20,"ip_address":"192.0.2.60","user_agent":"Mozilla/5.0","request_id":"req-7"}
{"timestamp":"2025-01-15T10:07:00Z","user_id":"frank","url":"/bad-status","status_code":"abc","response_time_ms":30,"ip_address":"192.0.2.70","user_agent":"Mozilla/5.0","request_id":"req-8"}
{"timestamp":"2025-01-15T10:08:00Z","user_id":"grace","url":"/negative","status_code":200,"response_time_ms":-1,"ip_address":"192.0.2.80","user_agent":"Mozilla/5.0","request_id":"req-9"}
{"timestamp":"2025-01-15T10:09:00Z","user_id":"hank","url":"/broken"
```

---

## `src/main/scala/com/example/traffic/config/TrafficJobConfig.scala`

```scala
package com.example.traffic.config

import com.typesafe.config.ConfigFactory

import java.io.File
import java.time.LocalDate
import scala.collection.JavaConverters._

final case class TrafficJobConfig(
    inputPaths: Seq[String],
    outputPath: String,
    quarantinePath: String,
    processingDate: LocalDate,
    applicationName: String,
    repartitionCount: Option[Int]
)

object TrafficJobConfig {

  def load(path: String): TrafficJobConfig = {
    val config = ConfigFactory.parseFile(new File(path)).resolve()
    val root = config.getConfig("traffic")

    val inputPaths = root.getStringList("inputPaths").asScala.toSeq.map(_.trim).filter(_.nonEmpty)
    require(inputPaths.nonEmpty, "traffic.inputPaths must contain at least one path")

    val outputPath = root.getString("outputPath").trim
    val quarantinePath = root.getString("quarantinePath").trim
    require(outputPath.nonEmpty, "traffic.outputPath must be non-empty")
    require(quarantinePath.nonEmpty, "traffic.quarantinePath must be non-empty")

    val processingDate = LocalDate.parse(root.getString("processingDate").trim)

    val applicationName =
      if (root.hasPath("applicationName")) root.getString("applicationName").trim
      else "daily-web-traffic-analytics"

    val repartitionCount =
      if (root.hasPath("repartitionCount")) {
        val n = root.getInt("repartitionCount")
        require(n > 0, "traffic.repartitionCount must be positive when provided")
        Some(n)
      } else None

    TrafficJobConfig(
      inputPaths = inputPaths,
      outputPath = outputPath,
      quarantinePath = quarantinePath,
      processingDate = processingDate,
      applicationName = applicationName,
      repartitionCount = repartitionCount
    )
  }
}
```

---

## `src/main/scala/com/example/traffic/io/PathGuard.scala`

```scala
package com.example.traffic.io

import java.net.URI
import java.nio.file.{Path, Paths}

object PathGuard {
  private val SupportedSchemes =
    Set("file", "hdfs", "s3", "s3a", "s3n", "gs", "abfs", "abfss", "wasb", "wasbs")

  def validateInputPath(path: String): String = {
    require(path != null && path.trim.nonEmpty, "Input path must be non-empty")
    val trimmed = path.trim
    val uri = new URI(trimmed)

    Option(uri.getScheme) match {
      case None =>
        rejectTraversal(trimmed)
        trimmed

      case Some(scheme) =>
        val lower = scheme.toLowerCase
        require(SupportedSchemes.contains(lower), s"Unsupported input path scheme: $scheme")
        rejectTraversal(Option(uri.getPath).getOrElse(""))
        trimmed
    }
  }

  def validateOutputBase(path: String): String = {
    require(path != null && path.trim.nonEmpty, "Output path must be non-empty")
    val trimmed = path.trim
    val uri = new URI(trimmed)

    Option(uri.getScheme) match {
      case None =>
        rejectTraversal(trimmed)
        Paths.get(trimmed).toAbsolutePath.normalize().toString

      case Some("file") =>
        rejectTraversal(Option(uri.getPath).getOrElse(""))
        Paths.get(uri).toAbsolutePath.normalize().toString

      case Some(scheme) =>
        val lower = scheme.toLowerCase
        require(SupportedSchemes.contains(lower), s"Unsupported output path scheme: $scheme")
        rejectTraversal(Option(uri.getPath).getOrElse(""))
        require(Option(uri.getAuthority).exists(_.nonEmpty), s"Object-storage output path requires authority/bucket: $path")
        trimmed.stripSuffix("/")
    }
  }

  def childUnderBase(base: String, child: String): String = {
    require(child != null && child.trim.nonEmpty, "Child path must be non-empty")
    require(!child.startsWith("/"), s"Child path must be relative, got: $child")
    rejectTraversal(child)

    val baseUri = new URI(base)

    Option(baseUri.getScheme) match {
      case None =>
        val basePath = Paths.get(base).toAbsolutePath.normalize()
        val childPath = basePath.resolve(child).normalize()
        require(childPath.startsWith(basePath), s"Resolved child path escapes base: $child")
        childPath.toString

      case Some("file") =>
        val basePath = Paths.get(baseUri).toAbsolutePath.normalize()
        val childPath = basePath.resolve(child).normalize()
        require(childPath.startsWith(basePath), s"Resolved child path escapes base: $child")
        childPath.toString

      case Some(_) =>
        val prefix = base.stripSuffix("/")
        s"$prefix/$child"
    }
  }

  private def rejectTraversal(path: String): Unit = {
    val parts = path.replace("\\", "/").split("/").filter(_.nonEmpty)
    require(!parts.contains(".."), s"Path traversal segments are not allowed: $path")
  }
}
```

---

## `src/main/scala/com/example/traffic/model/Schemas.scala`

```scala
package com.example.traffic.model

import org.apache.spark.sql.types._

object Schemas {

  val CorruptRecordColumn = "_corrupt_record"

  val RawInputSchema: StructType = StructType(
    Seq(
      StructField("timestamp", StringType, nullable = true),
      StructField("user_id", StringType, nullable = true),
      StructField("url", StringType, nullable = true),
      StructField("status_code", StringType, nullable = true),
      StructField("response_time_ms", StringType, nullable = true),
      StructField("ip_address", StringType, nullable = true),
      StructField("user_agent", StringType, nullable = true),
      StructField("request_id", StringType, nullable = true),
      StructField(CorruptRecordColumn, StringType, nullable = true)
    )
  )

  object ReasonCode {
    val CorruptRecord = "CORRUPT_RECORD"
    val MissingTimestamp = "MISSING_TIMESTAMP"
    val InvalidTimestamp = "INVALID_TIMESTAMP"
    val MissingUserId = "MISSING_USER_ID"
    val MissingUrl = "MISSING_URL"
    val MissingStatusCode = "MISSING_STATUS_CODE"
    val InvalidStatusCode = "INVALID_STATUS_CODE"
    val StatusCodeOutOfRange = "STATUS_CODE_OUT_OF_RANGE"
    val MissingResponseTime = "MISSING_RESPONSE_TIME_MS"
    val InvalidResponseTime = "INVALID_RESPONSE_TIME_MS"
    val NegativeResponseTime = "NEGATIVE_RESPONSE_TIME_MS"
    val MissingIpAddress = "MISSING_IP_ADDRESS"
    val MissingUserAgent = "MISSING_USER_AGENT"
    val MissingRequestId = "MISSING_REQUEST_ID"
    val OutOfProcessingDate = "OUT_OF_PROCESSING_DATE"
  }
}
```

---

## `src/main/scala/com/example/traffic/pipeline/TrafficPipeline.scala`

```scala
package com.example.traffic.pipeline

import com.example.traffic.config.TrafficJobConfig
import com.example.traffic.io.PathGuard
import com.example.traffic.model.Schemas
import com.example.traffic.model.Schemas.ReasonCode
import org.apache.spark.sql.expressions.Window
import org.apache.spark.sql.functions._
import org.apache.spark.sql.types.IntegerType
import org.apache.spark.sql.{Column, DataFrame, SparkSession}

import java.time.LocalDate

final case class ValidationResult(cleanWithDuplicates: DataFrame, quarantined: DataFrame)
final case class PipelineOutputs(clean: DataFrame, quarantined: DataFrame, metrics: Map[String, DataFrame])

object TrafficPipeline {

  def readRaw(spark: SparkSession, inputPaths: Seq[String]): DataFrame = {
    val safePaths = inputPaths.map(PathGuard.validateInputPath)
    spark.read
      .schema(Schemas.RawInputSchema)
      .option("mode", "PERMISSIVE")
      .option("columnNameOfCorruptRecord", Schemas.CorruptRecordColumn)
      .json(safePaths: _*)
  }

  def validateAndNormalize(raw: DataFrame, processingDate: LocalDate): ValidationResult = {
    val processingDateLiteral = lit(processingDate.toString)

    val timestampTrimmed = trim(col("timestamp"))
    val userIdTrimmed = trim(col("user_id"))
    val urlTrimmed = trim(col("url"))
    val statusTrimmed = trim(col("status_code"))
    val responseTrimmed = trim(col("response_time_ms"))
    val ipTrimmed = trim(col("ip_address"))
    val agentTrimmed = trim(col("user_agent"))
    val requestIdTrimmed = trim(col("request_id"))

    val timestampParsed = to_timestamp(timestampTrimmed)
    val statusParsed = statusTrimmed.cast(IntegerType)
    val responseParsed = responseTrimmed.cast(IntegerType)

    val enriched = raw
      .withColumn("timestamp_utc", timestampParsed)
      .withColumn("event_date", to_date(col("timestamp_utc")))
      .withColumn("status_code_int", statusParsed)
      .withColumn("response_time_ms_int", responseParsed)
      .withColumn(
        "normalized_url",
        when(
          lower(urlTrimmed).startsWith("http://") || lower(urlTrimmed).startsWith("https://"),
          coalesce(expr("parse_url(url, 'PATH')"), urlTrimmed)
        ).otherwise(regexp_extract(urlTrimmed, "^[^?]*", 0))
      )

    val corrupt = col(Schemas.CorruptRecordColumn).isNotNull

    def missing(c: Column): Column = c.isNull || length(trim(c)) === 0

    val nonCorruptReasons = array_remove(
      array
