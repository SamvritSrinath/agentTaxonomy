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
