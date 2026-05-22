const GENERATION_MODELS = [
  "moonshotai/kimi-k2.5",
  "openai/gpt-4o",
  "openai/gpt-5.5",
  "anthropic/claude-sonnet-4",
  "google/gemini-2.5-pro-preview"
] as const;

const JUDGE_MODELS = ["openai/gpt-4o", "openai/gpt-5.5", "moonshotai/kimi-k2.5"] as const;

export interface ModelSelectProps {
  id?: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  kind?: "generation" | "judge";
}

export function ModelSelect({
  id,
  label,
  value,
  onChange,
  disabled = false,
  kind = "generation"
}: ModelSelectProps) {
  const listId = `${id ?? label.replace(/\s+/g, "-").toLowerCase()}-models`;
  const suggestions = kind === "judge" ? JUDGE_MODELS : GENERATION_MODELS;

  return (
    <label htmlFor={id}>
      {label}
      <input
        id={id}
        type="text"
        list={listId}
        value={value}
        disabled={disabled}
        placeholder={kind === "judge" ? "Heuristic (leave empty)" : "provider/model"}
        onChange={(event) => onChange(event.target.value)}
      />
      <datalist id={listId}>
        {kind === "judge" ? <option value="" label="Heuristic (no LLM judge)" /> : null}
        {suggestions.map((option) => (
          <option key={option} value={option} />
        ))}
      </datalist>
    </label>
  );
}
