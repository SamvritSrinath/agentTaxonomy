import type { JobStatus } from "../api/types";

/** Async workbench jobs surfaced on the Jobs page and dashboard LLM counter. */
export const LLM_WORKBENCH_JOB_KINDS = new Set(["generate", "repo_run", "judge"]);

export function isLlmWorkbenchJob(job: JobStatus): boolean {
  return LLM_WORKBENCH_JOB_KINDS.has(job.kind);
}

export function isRunningJob(job: JobStatus): boolean {
  return job.status === "running" || job.status === "queued";
}

/** Resolve indexed run id from job metadata (judge sets early; repo/generate after ingest). */
export function resolveJobRunId(job: JobStatus): string | null {
  const meta = job.metadata_json ?? {};
  if (typeof meta.run_id === "string") {
    return meta.run_id;
  }
  const nested = (job.result ?? meta.result) as Record<string, unknown> | undefined;
  if (typeof nested?.run_id === "string") {
    return nested.run_id;
  }
  return null;
}

/** Human-readable job kind for the workbench queue. */
export function formatJobKind(job: JobStatus): string {
  if (job.kind === "repo_run") {
    const method = job.metadata_json?.execution_method;
    if (method === "model") {
      return "Repo generation (model)";
    }
    if (method === "agent") {
      return "Repo run (agent)";
    }
    return "Repo run";
  }
  if (job.kind === "generate") {
    return "Generate (generative)";
  }
  if (job.kind === "judge") {
    return "Judge";
  }
  return job.kind;
}

export function jobDetailLine(job: JobStatus): string | null {
  const meta = job.metadata_json ?? {};
  if (job.kind === "repo_run") {
    const model = meta.model as string | undefined;
    const instance = meta.instance_id as string | undefined;
    if (model && instance) {
      return `${instance} · ${model}`;
    }
    if (instance) {
      return instance;
    }
  }
  if (job.kind === "generate") {
    const model = meta.model as string | undefined;
    const instance = meta.instance_id as string | undefined;
    if (model && instance) {
      return `${instance} · ${model}`;
    }
  }
  if (job.kind === "judge") {
    const model = meta.judge_model as string | undefined;
    const evidence = meta.evidence_condition as string | undefined;
    if (model) {
      return model;
    }
    if (evidence) {
      return evidence.replace(/_/g, " ");
    }
    return "heuristic";
  }
  return null;
}
