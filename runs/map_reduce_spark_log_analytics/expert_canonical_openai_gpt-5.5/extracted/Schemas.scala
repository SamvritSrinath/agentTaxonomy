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
