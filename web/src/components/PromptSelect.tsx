import type { PromptVariant } from "../api/types";

export interface PromptSelectProps {
  id?: string;
  label: string;
  prompts: PromptVariant[];
  value: string;
  onChange: (promptId: string) => void;
  disabled?: boolean;
}

function promptLabel(prompt: PromptVariant): string {
  const variant = prompt.variant_name === "canonical" ? prompt.skill_level : prompt.variant_name;
  return `${variant} (${prompt.id.slice(0, 8)}…)`;
}

export function PromptSelect({ id, label, prompts, value, onChange, disabled = false }: PromptSelectProps) {
  return (
    <label htmlFor={id}>
      {label}
      <select
        id={id}
        value={value}
        disabled={disabled || prompts.length === 0}
        onChange={(event) => onChange(event.target.value)}
      >
        {prompts.length === 0 ? <option value="">No prompts indexed — run bootstrap</option> : null}
        {prompts.map((prompt) => (
          <option key={prompt.id} value={prompt.id}>
            {promptLabel(prompt)}
          </option>
        ))}
      </select>
    </label>
  );
}
