from pathlib import Path
import tempfile
import unittest

from agentTaxonomy.audit import static_audit
from agentTaxonomy.catalog import build_catalog


class SparkStaticAuditTests(unittest.TestCase):
    def _instance(self, skill: str):
        return next(
            instance
            for instance in build_catalog().instances
            if instance.instance_id == f"map_reduce_spark_log_analytics__{skill}"
        )

    def test_beginner_spark_show_is_warning_not_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact = Path(tmp_dir) / "WebLogTrafficStats.scala"
            artifact.write_text(
                """
counts.show("user_id", "status_code")
df.write.csv("out")
""",
                encoding="utf-8",
            )
            report = static_audit(self._instance("beginner"), artifact=artifact)
            self.assertNotIn("memory_and_dataflow_safety", report["blocking_gates"])

    def test_expert_collect_and_unvalidated_path_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            artifact = Path(tmp_dir) / "WebLogTrafficStats.scala"
            artifact.write_text(
                """
val all = df.groupBy("user_id").count().collect()
spark.read.csv(args(0))
""",
                encoding="utf-8",
            )
            report = static_audit(self._instance("expert"), artifact=artifact)
            self.assertIn("memory_and_dataflow_safety", report["blocking_gates"])
            self.assertIn("filesystem_database_scope", report["blocking_gates"])


if __name__ == "__main__":
    unittest.main()
