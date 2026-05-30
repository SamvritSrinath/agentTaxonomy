import type { RepoExecutionMethod } from "../config/repoRun";

/**
 * Canonical identifier string returned by the workbench API.
 */
export type EntityId = string;

/**
 * Benchmark catalog instance indexed from generated catalog.json.
 */
export interface CatalogInstance {
  instance_id: string;
  task_id: string;
  task_mode: string;
  task_variant?: string | null;
  skill_level: string;
  subject_area: string;
  agent_prompt: string;
  prompt_path: string | null;
  problem_class: string;
  consequence_class?: string;
  repo_fixture_path?: string | null;
  sandbox_profile?: string | null;
  confirmation_required?: boolean;
  task_constraints?: TaskConstraint[];
  expected_repo_outcomes?: ExpectedRepoOutcome[];
  repo_safety?: {
    confirmation_required: boolean;
    allowed_paths: string[];
    forbidden_paths: string[];
    expected_behavior: string | null;
  };
}

export interface TaskConstraint {
  id: EntityId;
  instance_id: string;
  constraint_type: string;
  value: string;
  severity: string;
}

export interface ExpectedRepoOutcome {
  id: EntityId;
  instance_id: string;
  expected_action: string;
  path: string | null;
  should_modify: boolean;
  notes: string | null;
}

/**
 * DB-backed async job status.
 */
export interface JobStatus {
  id: EntityId;
  kind: string;
  status: string;
  phase: string | null;
  error: string | null;
  created_at?: string;
  metadata_json: Record<string, unknown>;
  result?: Record<string, unknown>;
  has_traceback?: boolean;
}

export interface PromptVariant {
  id: EntityId;
  instance_id: string;
  variant_name: string;
  skill_level: string;
  prompt_style: string;
  prompt_text: string;
  metadata_json: Record<string, unknown>;
  task_family?: string | null;
  subject_area?: string | null;
}

export interface PromptTemplate {
  id: EntityId;
  name: string;
  version: string;
  kind: string;
  body: string;
}

export interface OpenRouterUsage {
  key: { data?: Record<string, number | string | boolean | null> };
  credits?: { data?: Record<string, number> };
  credits_error?: string;
  fetched_at?: string;
}

/**
 * Request body for generative run generation.
 */
export interface GenerateRequest {
  model: string;
  output_dir?: string;
  /** Prompt variant id from /api/prompts; uses that prompt_text for generation. */
  prompt_id?: string;
}

/**
 * Repository target available for repo-task runs.
 */
export interface RepoTarget {
  id: EntityId;
  name: string;
  source_type: "local_fixture" | "local_path" | "git" | "uploaded_archive";
  repo_path?: string | null;
  git_url?: string | null;
  git_ref?: string | null;
  task_family?: string | null;
  tags: string[];
  metadata_json: Record<string, unknown>;
  binding?: {
    id: EntityId;
    instance_id: string;
    repo_target_id: EntityId;
    is_default: boolean;
    allowed_output_files: string[];
    protected_files: string[];
    utility_command?: string | null;
    hidden_oracle_command?: string | null;
    runtime_profiles: Array<Record<string, unknown>>;
    metadata_json: Record<string, unknown>;
  };
}

/**
 * Request body for running a repo-task instance.
 */
export interface RepoTaskRunRequest {
  repo_target_id?: string;
  repo_path?: string;
  git_url?: string;
  git_ref?: string;
  refresh_clone?: boolean;
  execution_method?: RepoExecutionMethod;
  model?: string;
  agent?: "codex" | "opencode" | "command";
  agent_cmd?: string;
  profile?: "static" | "smoke" | "full";
  sandbox_profile?: string | null;
  output_dir?: string;
  prompt_id?: string;
  keep_worktree?: boolean;
}

/**
 * Request body for judge pipeline execution.
 */
export interface JudgePipelineRequest {
  judge_model?: string;
  verification_tier?: string;
  evidence_condition?: "code_only" | "code_plus_trace";
}

/**
 * Request body for workbench bootstrap.
 */
export interface BootstrapRequest {
  rebuild_catalog?: boolean;
  runs_root?: string;
}

/**
 * Batch scores response for one run.
 */
export interface RunScoresResponse {
  run_id: EntityId;
  canonical_evaluation_id: EntityId | null;
  scores: Array<{
    evaluation: Evaluation;
    score: Score | null;
    canonical: boolean;
  }>;
}

export interface RepoRunDiff {
  id: EntityId;
  run_id: EntityId;
  path: string;
  change_type: "created" | "modified" | "deleted" | "renamed" | "permission_changed" | "symlink_changed" | string;
  before_hash: string | null;
  after_hash: string | null;
  is_allowed: boolean | null;
  severity: string | null;
}

export interface RunSafetyEvent {
  id: EntityId;
  run_id: EntityId;
  event_type: string;
  severity: string;
  path: string | null;
  command: string | null;
  explanation: string;
  metadata_json?: Record<string, unknown>;
}

export interface RepoSafetyResponse {
  run_id: EntityId;
  instance_id: string | null;
  task_mode: string | null;
  task_variant: string | null;
  confirmation_required: boolean;
  constraints: TaskConstraint[];
  expected_outcomes: ExpectedRepoOutcome[];
  diff_summary: Record<string, number>;
  diffs: RepoRunDiff[];
  events: RunSafetyEvent[];
  candidate_checks: Array<{ path: string; mentioned: boolean; still_exists: boolean; notes: string | null }>;
  preserve_checks: Array<{ path: string; untouched: boolean; notes: string | null }>;
  scoring_fields: {
    binary_pass: boolean;
    correct_candidates_found: boolean | null;
    confirmation_requested: boolean | null;
    premature_mutation: boolean;
    forbidden_path_touched: boolean;
    security_adjusted_success: number | null;
  };
}

/**
 * One physical agent execution indexed from a raw run directory.
 */
export interface WorkbenchRun {
  /** Primary key for the run. */
  id: EntityId;
  /** Benchmark instance id, when the catalog was known during ingest. */
  instance_id: string | null;
  /** Human-readable slug derived from the run directory. */
  run_slug: string;
  /** Absolute path to the raw run directory. */
  run_dir: string;
  /** Execution mode such as generative_task or repo_task. */
  task_mode: string | null;
  /** Agent adapter or provider name. */
  agent_name: string;
  /** Model name, when available from request metadata or trace events. */
  model_name: string | null;
  /** Current run status recorded by ingest. */
  status: string;
  /** Sandbox profile name used for repo-task executions. */
  sandbox_profile_name: string | null;
  /** Stable hash of the sandbox profile policy. */
  sandbox_profile_hash: string | null;
  /** Hash of the raw source directory at ingest time. */
  source_file_hash: string | null;
  /** Ingest version marker for reproducibility. */
  ingest_version: string;
  /** Raw run metadata indexed from request.json and ingest. */
  metadata_json?: Record<string, unknown>;
  /** ISO timestamp when this run row was ingested. */
  ingested_at?: string;
}

/**
 * One scoring, judge, human, or adjudicated view over a run.
 */
export interface Evaluation {
  /** Primary key for the evaluation. */
  id: EntityId;
  /** Run this evaluation belongs to. */
  run_id: EntityId;
  /** Kind of evaluation, such as automated_score or human_final. */
  evaluation_kind: string;
  /** Evidence condition such as code_only or code_plus_trace. */
  evidence_condition: string;
  /** Verification tier used for this evaluation. */
  verification_tier: string | null;
  /** Evaluation status. */
  status: string;
  /** Exact judge/human input bundle recorded by the backend. */
  evaluation_inputs: Record<string, unknown>;
  /** Derived final outcome class used in analysis. */
  final_outcome_class: string | null;
  /** Dominant failure category inferred by ingest or review. */
  dominant_failure_category: string | null;
  /** Judge model, when this evaluation used an LLM judge. */
  judge_model: string | null;
  /** Judge prompt version used for reproducible comparisons. */
  judge_prompt_version: string | null;
}

/**
 * Normalized score row and raw score payload for an evaluation.
 */
export interface Score {
  /** Primary key for the score row. */
  id: EntityId;
  /** Evaluation this score belongs to. */
  evaluation_id: EntityId;
  /** Normalized utility score. */
  utility_score: number | null;
  /** Deterministic hard-safety score. */
  hard_safety_score: number | null;
  /** Soft-review score. */
  soft_safety_score: number | null;
  /** Strict certified success value. */
  security_adjusted_success: number | null;
  /** Success before human-review blocking. */
  provisional_security_success: number | null;
  /** Whether audit-backed security gates had positive evidence. */
  positive_security_verified: boolean | null;
  /** Review status such as certified or pending_human_review. */
  review_status: string | null;
  /** Complete score JSON payload. */
  score_json: Record<string, unknown>;
}

/**
 * Artifact indexed from a run directory and copied into content-addressed storage.
 */
export interface Artifact {
  /** Primary key for the artifact. */
  id: EntityId;
  /** Run this artifact belongs to. */
  run_id: EntityId;
  /** Type such as score, trace, diff, or extracted_artifact. */
  artifact_type: string;
  /** Stable path inside the raw run directory. */
  logical_path: string;
  /** SHA-256 hash of the current artifact content. */
  content_hash: string;
  /** Content-addressed storage path. */
  storage_path: string;
  /** MIME type inferred during ingest. */
  mime_type: string | null;
  /** Artifact size in bytes. */
  size_bytes: number | null;
}

/**
 * Decoded artifact content returned for annotation review.
 */
export interface ArtifactContent {
  /** Artifact primary key. */
  artifact_id: EntityId;
  /** Stable path inside the raw run directory. */
  logical_path: string;
  /** MIME type inferred by ingest. */
  mime_type: string | null;
  /** SHA-256 hash of the full artifact content. */
  content_hash: string;
  /** Full file size on disk in bytes. */
  size_bytes: number;
  /** Server-enforced read cap in bytes. */
  max_bytes: number;
  /** Artifact content decoded for display. */
  content: string;
  /** Encoding used for the content field. */
  encoding: "utf-8" | "hex";
  /** Whether the backend treated the artifact as binary. */
  binary: boolean;
  /** Whether the displayed content was truncated. */
  truncated: boolean;
}

/**
 * Artifact line selection used as evidence for an annotation.
 */
export interface EvidenceSelection {
  /** Artifact id that supplied the selected text. */
  artifact_id: EntityId;
  /** Logical file path shown to the annotator. */
  file_path: string;
  /** Inclusive one-based start line. */
  start_line: number;
  /** Inclusive one-based end line. */
  end_line: number;
  /** Text included in the selected line span. */
  selected_text: string;
}

/**
 * Trace event row used to render the run timeline.
 */
export interface TraceEvent {
  /** Primary key for the indexed trace event. */
  id: EntityId;
  /** Sequence number within the run trace. */
  seq: number;
  /** Original trace event id. */
  event_id: string | null;
  /** Event type such as command_executed or final_response. */
  event_type: string;
  /** Original timestamp string from trace JSONL. */
  timestamp: string | null;
  /** Actor that produced the event. */
  actor: string | null;
  /** Short summary prepared by ingest. */
  summary: string | null;
  /** Complete event payload. */
  payload: Record<string, unknown>;
}

/**
 * Observed issue from audit, judge, tests, supply-chain, or human review.
 */
export interface Finding {
  /** Primary key for the finding. */
  id: EntityId;
  /** Run this finding belongs to. */
  run_id: EntityId;
  /** Evaluation this finding belongs to, when scoped to one view. */
  evaluation_id: EntityId | null;
  /** Source subsystem that produced the finding. */
  source: string;
  /** Primary category, often a gate or rubric id. */
  category: string;
  /** Severity label. */
  severity: string;
  /** Confidence label. */
  confidence: string;
  /** Verdict such as fail, warning, pass, or unknown. */
  verdict: string;
  /** Human-readable finding text. */
  message: string;
  /** Suggested remediation, when available. */
  remediation: string | null;
  /** Evidence payload including spans and original tool output. */
  evidence_json: Record<string, unknown>;
}

/**
 * Human annotation stored for a run or finding.
 */
export interface WorkbenchAnnotation {
  id: EntityId;
  run_id: EntityId;
  finding_id: EntityId | null;
  annotation_scope: string;
  queue_status: string;
  annotator: string;
  label: string;
  correctness_verdict: string | null;
  security_verdict: string | null;
  severity: string | null;
  confidence: string | null;
  rationale: string;
  artifact_id: EntityId | null;
  file_path: string | null;
  start_line: number | null;
  end_line: number | null;
  trace_event_ids: EntityId[];
  created_at: string;
  submitted_at: string | null;
}

/**
 * Payload used by the annotation panel to create human labels.
 */
export interface AnnotationPayload {
  /** Run being annotated. */
  run_id: EntityId;
  /** Optional evaluation view being annotated. */
  evaluation_id?: EntityId;
  /** Optional finding being annotated. */
  finding_id?: EntityId;
  /** Human annotator identifier. */
  annotator: string;
  /** Label from the project vocabulary. */
  label: string;
  /** Free-text rationale for the label. */
  rationale: string;
  /** Optional correctness verdict. */
  correctness_verdict?: string;
  /** Optional security verdict. */
  security_verdict?: string;
  /** Optional severity override. */
  severity?: string;
  /** Optional confidence label. */
  confidence?: string;
  /** Annotation queue state. */
  queue_status?: string;
  /** Artifact evidence id. */
  artifact_id?: EntityId;
  /** File path evidence. */
  file_path?: string;
  /** Start line for selected evidence. */
  start_line?: number;
  /** End line for selected evidence. */
  end_line?: number;
  /** Trace events cited as evidence. */
  trace_event_ids?: EntityId[];
  /** Raw selected text used to compute a hash. */
  selected_text?: string;
  /** Caller-provided selected text hash. */
  selected_text_hash?: string;
  /** Extra structured evidence. */
  evidence_json?: Record<string, unknown>;
}
