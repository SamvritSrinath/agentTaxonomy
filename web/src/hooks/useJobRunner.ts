import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { pollJob } from "../api/client";
import { resolveJobRunId } from "../config/jobs";
import type { JobStatus } from "../api/types";

export interface UseJobRunnerOptions {
  onRefresh?: () => void;
  /** Navigate to /runs/:id when a generate or repo_run job returns run_id. */
  navigateOnGenerate?: boolean;
}

export function useJobRunner(options: UseJobRunnerOptions = {}) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [phase, setPhase] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const waitForJob = useCallback(async (jobId: string): Promise<JobStatus> => {
    // Match server OpenRouter timeout (~240s) plus harness/ingest slack.
    for (let attempt = 0; attempt < 330; attempt += 1) {
      const job = await pollJob(jobId);
      setPhase(job.phase ?? job.status);
      if (job.status === "succeeded") {
        return job;
      }
      if (job.status === "failed") {
        throw new Error(job.error ?? "job failed");
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
    throw new Error("job timed out");
  }, []);

  const runJob = useCallback(
    async (start: () => Promise<{ job_id: string }>) => {
      setBusy(true);
      setError(null);
      try {
        const started = await start();
        const job = await waitForJob(started.job_id);
        const runId = resolveJobRunId(job);
        if (options.navigateOnGenerate && (job.kind === "generate" || job.kind === "repo_run") && runId) {
          navigate(`/runs/${runId}`);
        }
        options.onRefresh?.();
        return job;
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        setError(message);
        throw err;
      } finally {
        setBusy(false);
        setPhase(null);
      }
    },
    [waitForJob, options.onRefresh, options.navigateOnGenerate, navigate]
  );

  return { busy, phase, error, runJob, setError };
}
