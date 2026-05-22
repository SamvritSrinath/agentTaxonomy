from pathlib import Path
import tempfile
import unittest

from agentTaxonomy.artifact_extract import extract_markdown_artifacts


class ArtifactExtractTests(unittest.TestCase):
    def test_extracts_fenced_blocks_by_language(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            markdown = Path(tmp_dir) / "agent_output.md"
            output_dir = Path(tmp_dir) / "extracted"
            markdown.write_text(
                """
# Solution

```scala
object WebLogTrafficStats {
  def main(args: Array[String]): Unit = println("ok")
}
```

```csv
user_id,status_code
1,200
```

```bash
spark-submit --class WebLogTrafficStats app.jar
```
""",
                encoding="utf-8",
            )
            manifest = extract_markdown_artifacts(markdown, output_dir)

            self.assertEqual(manifest["block_count"], 3)
            self.assertTrue((output_dir / "WebLogTrafficStats.scala").exists())
            self.assertTrue(any(path.suffix == ".csv" for path in output_dir.iterdir()))
            self.assertTrue(any(path.suffix == ".sh" for path in output_dir.iterdir()))

    def test_reextract_replaces_prior_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            markdown = Path(tmp_dir) / "agent_output.md"
            output_dir = Path(tmp_dir) / "extracted"
            markdown.write_text("```scala\nobject Demo { }\n```\n", encoding="utf-8")
            extract_markdown_artifacts(markdown, output_dir)
            first_count = len(list(output_dir.iterdir()))

            markdown.write_text(
                "```scala\nobject Demo { }\n```\n\n```bash\necho hi\n```\n",
                encoding="utf-8",
            )
            extract_markdown_artifacts(markdown, output_dir)
            second_count = len(list(output_dir.iterdir()))
            names = {path.name for path in output_dir.iterdir()}

            self.assertEqual(first_count, 1)
            self.assertEqual(second_count, 2)
            self.assertNotIn("Demo_1.scala", names)
            self.assertTrue(any(name.endswith(".sh") for name in names))

    def test_mislabeled_scala_build_sbt_fence_becomes_build_sbt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            markdown = Path(tmp_dir) / "agent_output.md"
            output_dir = Path(tmp_dir) / "extracted"
            markdown.write_text(
                """
## `build.sbt`

```scala
lazy val sparkVersion = "3.5.1"
libraryDependencies ++= Seq(
  "org.apache.spark" %% "spark-sql" % sparkVersion
)
```
""",
                encoding="utf-8",
            )
            extract_markdown_artifacts(markdown, output_dir)
            self.assertTrue((output_dir / "build.sbt").exists())


if __name__ == "__main__":
    unittest.main()
