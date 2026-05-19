ThisBuild / scalaVersion := "2.12.18"

lazy val root = (project in file("."))
  .settings(
    name := "weblog-traffic-stats",
    version := "0.1.0",
    libraryDependencies += "org.apache.spark" %% "spark-sql" % "3.5.1" % "provided"
  )
