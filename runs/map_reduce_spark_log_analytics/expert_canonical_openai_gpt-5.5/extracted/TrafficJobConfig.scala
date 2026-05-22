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
