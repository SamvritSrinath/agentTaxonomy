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


if __name__ == "__main__":
    unittest.main()
