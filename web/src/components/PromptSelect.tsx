import type { PromptVariant } from "../api/types";
import { promptDisplayLabel, sortPromptVariants } from "../utils/promptLabels";

const CATALOG_PROMPT_VALUE = "";
import { Combobox } from "./Combobox";

export interface PromptSelectProps {
  id?: string;
  label: string;
  prompts: PromptVariant[];
  value: string;
  onChange: (promptId: string) => void;
  disabled?: boolean;
  /** Skill level for catalog default label, e.g. "beginner (catalog)". */
  catalogSkillLevel?: string | null;
}

export function PromptSelect({
  id,
  label,
  prompts,
  value,
  onChange,
  disabled = false,
  catalogSkillLevel = null
}: PromptSelectProps) {
  const sorted = sortPromptVariants(prompts);
  const catalogLabel = catalogSkillLevel ? `${catalogSkillLevel} (catalog)` : "Catalog prompt";
  const options = [
    { value: CATALOG_PROMPT_VALUE, label: catalogLabel },
    ...sorted.map((prompt) => ({
      value: prompt.id,
      label: promptDisplayLabel(prompt)
    }))
  ];

  return (
    <Combobox
      id={id}
      label={label}
      value={value}
      options={options}
      onChange={onChange}
      disabled={disabled}
      placeholder="Select prompt variant…"
      emptyMessage="No prompts match"
    />
  );
}

/** Resolve display label for a prompt id. */
export function promptLabelForId(prompts: PromptVariant[], promptId: string): string | null {
  const prompt = prompts.find((p) => p.id === promptId);
  return prompt ? promptDisplayLabel(prompt) : null;
}
