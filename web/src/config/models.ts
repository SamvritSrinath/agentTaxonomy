export interface ModelOption {
  id: string;
  label: string;
}

export const DEFAULT_GENERATION_MODEL = "moonshotai/kimi-k2.6";

export const GENERATION_MODELS: ModelOption[] = [
  { id: "moonshotai/kimi-k2.6", label: "Kimi K2.6" },
  { id: "moonshotai/kimi-k2.5", label: "Kimi K2.5" },
  { id: "minimax/minimax-m2.7", label: "Minimax 2.7" },
  { id: "minimax/minimax-m2.6", label: "Minimax 2.6" },
  { id: "z-ai/glm-5.1", label: "GLM 5.1" },
  { id: "deepseek/deepseek-v4-flash", label: "Deepseek V4 Flash" },
  { id: "deepseek/deepseek-v4-pro", label: "Deepseek V4 Pro" },
  { id: "qwen/qwen-3.6-plus", label: "Qwen 3.6 Plus" },
  { id: "anthropic/claude-sonnet-4.6", label: "Claude Sonnet 4.6" },
  { id: "anthropic/claude-opus-4.7", label: "Claude Opus 4.7" },
  { id: "openai/gpt-5.5", label: "GPT 5.5" },
  { id: "openai/gpt-5.4", label: "GPT 5.4" },
  { id: "openai/gpt-5-mini", label: "GPT 5 mini" },
  { id: "google/gemma-4-31b", label: "Gemma 4 31B" },
  { id: "google/gemma-4-26b-a4b", label: "Gemma 4 26B A4B" },
  { id: "openai/gpt-4o", label: "GPT 4o" },
  { id: "anthropic/claude-sonnet-4", label: "Claude Sonnet 4" },
  { id: "google/gemini-2.5-pro-preview", label: "Gemini 2.5 Pro" }
];

export const JUDGE_MODELS: ModelOption[] = [
  { id: "", label: "Heuristic (no LLM judge)" },
  { id: "openai/gpt-5.5", label: "GPT 5.5" },
  { id: "openai/gpt-5.4", label: "GPT 5.4" },
  { id: "anthropic/claude-sonnet-4.6", label: "Claude Sonnet 4.6" },
  { id: "openai/gpt-4o", label: "GPT 4o" },
  { id: "moonshotai/kimi-k2.6", label: "Kimi K2.6" },
  { id: "moonshotai/kimi-k2.5", label: "Kimi K2.5" }
];

export function generationModelOptions(): { value: string; label: string }[] {
  return GENERATION_MODELS.map((m) => ({ value: m.id, label: `${m.label} (${m.id})` }));
}

export function judgeModelOptions(): { value: string; label: string }[] {
  return JUDGE_MODELS.map((m) => ({ value: m.id, label: m.label }));
}
