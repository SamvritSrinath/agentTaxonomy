/** Default agent CLI templates (matches CLI `_default_repo_agent_cmd`). */
export const DEFAULT_REPO_AGENT_CMD: Record<"codex" | "opencode", string> = {
  codex: 'codex exec --full-auto --cd {worktree} "$(cat {prompt_file})"',
  opencode:
    'opencode run --dir {worktree} -f {prompt_file} --dangerously-skip-permissions "Follow the attached task prompt and edit the repo."'
};

export type RepoExecutionMethod = "model" | "agent";
