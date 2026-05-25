"""Stale job reconciliation when API workers are orphaned."""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta

from agentTaxonomy.db.jobs import create_job, get_job, reconcile_stale_jobs
from agentTaxonomy.db.models import JobRecord
from agentTaxonomy.db.session import migrate_database, session_scope


class StaleJobTests(unittest.TestCase):
    def test_reconcile_marks_old_running_repo_run_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            database_url = f"sqlite:///{tmp_dir}/jobs.sqlite"
            migrate_database(database_url)
            with session_scope(database_url) as session:
                job = create_job(session, kind="repo_run", metadata={"instance_id": "test"})
                row = session.get(JobRecord, job["id"])
                assert row is not None
                row.status = "running"
                row.phase = "openrouter"
                row.started_at = datetime.now(UTC) - timedelta(seconds=400)
                session.flush()
                reconciled = reconcile_stale_jobs(session, now=datetime.now(UTC))
                self.assertEqual(reconciled, [job["id"]])
                updated = get_job(session, job["id"])
                assert updated is not None
                self.assertEqual(updated["status"], "failed")
                self.assertIn("API restarted", updated["error"] or "")


if __name__ == "__main__":
    unittest.main()
