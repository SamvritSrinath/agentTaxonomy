import type {
  AnnotationPayload,
  Artifact,
  ArtifactContent,
  BootstrapRequest,
  CatalogInstance,
  Evaluation,
  Finding,
  GenerateRequest,
  JobStatus,
  JudgePipelineRequest,
  RepoSafetyResponse,
  RepoTarget,
  RepoTaskRunRequest,
  RunScoresResponse,
  Score,
  TraceEvent,
  WorkbenchAnnotation,
  WorkbenchRun
} from "./types";

export const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8080";

/**
 * Fetch JSON from the workbench API and raise readable errors for failed calls.
 */
export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${message}`);
  }
  return (await response.json()) as T;
}

export function listRuns(): Promise<WorkbenchRun[]> {
  return fetchJson<WorkbenchRun[]>("/api/runs");
}

export function listCatalog(): Promise<CatalogInstance[]> {
  return fetchJson<CatalogInstance[]>("/api/catalog");
}

export function getInstance(instanceId: string): Promise<CatalogInstance> {
  return fetchJson<CatalogInstance>(`/api/instances/${instanceId}`);
}

export function getRun(runId: string): Promise<WorkbenchRun> {
  return fetchJson<WorkbenchRun>(`/api/runs/${runId}`);
}

export function listEvaluations(runId: string): Promise<Evaluation[]> {
  return fetchJson<Evaluation[]>(`/api/runs/${runId}/evaluations`);
}

export function listRunScores(runId: string): Promise<RunScoresResponse> {
  return fetchJson<RunScoresResponse>(`/api/runs/${runId}/scores`);
}

export function getRepoSafety(runId: string): Promise<RepoSafetyResponse> {
  return fetchJson<RepoSafetyResponse>(`/api/runs/${runId}/repo-safety`);
}

export function getEvaluationScore(evaluationId: string): Promise<Score> {
  return fetchJson<Score>(`/api/evaluations/${evaluationId}/score`);
}

export function listArtifacts(runId: string): Promise<Artifact[]> {
  return fetchJson<Artifact[]>(`/api/runs/${runId}/artifacts`);
}

export function getArtifactContent(artifactId: string, maxBytes = 1_000_000): Promise<ArtifactContent> {
  return fetchJson<ArtifactContent>(`/api/artifacts/${artifactId}/content?max_bytes=${maxBytes}`);
}

export function listTrace(runId: string): Promise<TraceEvent[]> {
  return fetchJson<TraceEvent[]>(`/api/runs/${runId}/trace`);
}

export function listFindings(runId: string): Promise<Finding[]> {
  return fetchJson<Finding[]>(`/api/runs/${runId}/findings`);
}

export function listRunAnnotations(runId: string): Promise<WorkbenchAnnotation[]> {
  return fetchJson<WorkbenchAnnotation[]>(`/api/runs/${runId}/annotations`);
}

export function createAnnotation(payload: AnnotationPayload): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(`/api/runs/${payload.run_id}/annotations`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function generateForInstance(
  instanceId: string,
  request: GenerateRequest
): Promise<{ job_id: string; status: string; prompt_id?: string | null }> {
  return fetchJson(`/api/instances/${instanceId}/generate`, {
    method: "POST",
    body: JSON.stringify(request)
  });
}

export function generateForPrompt(
  promptId: string,
  request: GenerateRequest
): Promise<{ job_id: string; status: string; prompt_id?: string | null }> {
  return fetchJson(`/api/prompts/${promptId}/generate`, {
    method: "POST",
    body: JSON.stringify(request)
  });
}

export function listRepoTargets(params?: {
  instance_id?: string;
  task_family?: string;
}): Promise<RepoTarget[]> {
  const query = new URLSearchParams();
  if (params?.instance_id) query.set("instance_id", params.instance_id);
  if (params?.task_family) query.set("task_family", params.task_family);
  const suffix = query.toString() ? `?${query}` : "";
  return fetchJson<RepoTarget[]>(`/api/repo-targets${suffix}`);
}

export function listRepoTargetsForInstance(instanceId: string): Promise<RepoTarget[]> {
  return fetchJson<RepoTarget[]>(`/api/instances/${encodeURIComponent(instanceId)}/repo-targets`);
}

export function runRepoTaskForInstance(
  instanceId: string,
  request: RepoTaskRunRequest
): Promise<{ job_id: string; status: string; run_id?: string | null }> {
  return fetchJson(`/api/instances/${encodeURIComponent(instanceId)}/repo-runs`, {
    method: "POST",
    body: JSON.stringify(request)
  });
}

export function runJudgePipeline(
  runId: string,
  request: JudgePipelineRequest
): Promise<{ job_id: string; status: string }> {
  return fetchJson(`/api/runs/${runId}/judge-pipeline`, {
    method: "POST",
    body: JSON.stringify(request)
  });
}

export function bootstrapWorkbench(request: BootstrapRequest = {}): Promise<{ job_id: string; status: string }> {
  return fetchJson("/api/bootstrap", {
    method: "POST",
    body: JSON.stringify(request)
  });
}

export function pollJob(jobId: string): Promise<JobStatus> {
  return fetchJson<JobStatus>(`/api/jobs/${jobId}`);
}

export function jobTracebackUrl(jobId: string): string {
  return `${API_BASE}/api/jobs/${encodeURIComponent(jobId)}/traceback`;
}

export function ingestCatalog(catalogPath = "benchmark/generated/catalog.json"): Promise<Record<string, unknown>> {
  return fetchJson("/api/catalog/ingest", {
    method: "POST",
    body: JSON.stringify({ catalog_path: catalogPath })
  });
}

export function ingestRun(runDir: string, newIngestVersion = false): Promise<{ job_id: string; status: string }> {
  return fetchJson("/api/runs/ingest", {
    method: "POST",
    body: JSON.stringify({ run_dir: runDir, new_ingest_version: newIngestVersion })
  });
}

export function rescoreRun(
  runId: string,
  evidenceCondition: string
): Promise<{ job_id: string; status: string }> {
  return fetchJson("/api/evaluations/rescore", {
    method: "POST",
    body: JSON.stringify({ run_id: runId, evidence_condition: evidenceCondition })
  });
}

export function getHealth(): Promise<{ status: string; database_url: string }> {
  return fetchJson("/api/health");
}

export function getOpenRouterUsage(): Promise<import("./types").OpenRouterUsage> {
  return fetchJson("/api/openrouter/usage");
}

export function listPrompts(params?: {
  instance_id?: string;
  skill_level?: string;
  task_family?: string;
}): Promise<import("./types").PromptVariant[]> {
  const query = new URLSearchParams();
  if (params?.instance_id) query.set("instance_id", params.instance_id);
  if (params?.skill_level) query.set("skill_level", params.skill_level);
  if (params?.task_family) query.set("task_family", params.task_family);
  const suffix = query.toString() ? `?${query}` : "";
  return fetchJson(`/api/prompts${suffix}`);
}

export function getPrompt(promptId: string): Promise<import("./types").PromptVariant> {
  return fetchJson(`/api/prompts/${promptId}`);
}

export function createPrompt(body: {
  instance_id: string;
  variant_name: string;
  prompt_text: string;
  skill_level?: string;
  prompt_style?: string;
}): Promise<import("./types").PromptVariant> {
  return fetchJson("/api/prompts", { method: "POST", body: JSON.stringify(body) });
}

export function updatePrompt(
  promptId: string,
  body: { prompt_text?: string; variant_name?: string; metadata?: Record<string, unknown> }
): Promise<import("./types").PromptVariant> {
  return fetchJson(`/api/prompts/${promptId}`, { method: "PUT", body: JSON.stringify(body) });
}

export function duplicatePrompt(
  promptId: string,
  variantName?: string
): Promise<import("./types").PromptVariant> {
  return fetchJson(`/api/prompts/${promptId}/duplicate`, {
    method: "POST",
    body: JSON.stringify({ variant_name: variantName ?? null })
  });
}

export function listPromptTemplates(): Promise<import("./types").PromptTemplate[]> {
  return fetchJson("/api/prompt-templates");
}

export function listJobs(params?: {
  limit?: number;
  status?: string;
  kind?: string;
}): Promise<import("./types").JobStatus[]> {
  const query = new URLSearchParams();
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.status) query.set("status", params.status);
  if (params?.kind) query.set("kind", params.kind);
  const suffix = query.toString() ? `?${query}` : "";
  return fetchJson(`/api/jobs${suffix}`);
}

export function exportTable(name: string): Promise<{ path: string }> {
  return fetchJson(`/api/exports/${name}`);
}

export interface CreateCatalogTaskRequest {
  task_id: string;
  subject_area: string;
  problem_class: string;
  beginner_prompt: string;
  intermediate_prompt?: string;
  expert_prompt?: string;
  language?: string;
  tags?: string[];
  rebuild_catalog?: boolean;
  ingest_catalog?: boolean;
}

export function createCatalogTask(
  body: CreateCatalogTaskRequest
): Promise<{
  task_id: string;
  task_dir: string;
  instance_ids: string[];
  catalog_path?: string;
}> {
  return fetchJson("/api/catalog/tasks", { method: "POST", body: JSON.stringify(body) });
}

export function updateCanonicalPrompt(
  instanceId: string,
  body: { prompt_text: string; rebuild_catalog?: boolean; ingest_catalog?: boolean }
): Promise<{ instance_id: string; prompt_path: string; catalog_path?: string }> {
  return fetchJson(`/api/instances/${encodeURIComponent(instanceId)}/canonical-prompt`, {
    method: "PUT",
    body: JSON.stringify(body)
  });
}
