Below is a complete small Spark/Scala batch pipeline PRD implementation with source, tests, config, sample data, expected outputs, and run notes.

---

## Project layout
---

## `build.sbt`
---

## `conf/local.conf`
---

## `data/sample-input.jsonl`
---

## `src/main/scala/com/example/traffic/config/TrafficJobConfig.scala`
---

## `src/main/scala/com/example/traffic/io/PathGuard.scala`
---

## `src/main/scala/com/example/traffic/model/Schemas.scala`
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
