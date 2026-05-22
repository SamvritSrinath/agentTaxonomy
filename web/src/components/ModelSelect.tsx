import { generationModelOptions, judgeModelOptions } from "../config/models";
import { Combobox } from "./Combobox";

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
  const options = kind === "judge" ? judgeModelOptions() : generationModelOptions();
  const isJudge = kind === "judge";
  const hint = isJudge
    ? value.trim()
      ? "OpenRouter LLM judge — any provider/model slug is sent as-is."
      : "Heuristic judge — no OpenRouter API call for soft scoring."
    : null;

  return (
    <div className="model-select-wrap">
      <Combobox
        id={id}
        label={label}
        value={value}
        options={options}
        onChange={onChange}
        disabled={disabled}
        allowCustomValue
        placeholder={isJudge ? "Heuristic (leave empty)" : "provider/model"}
        emptyMessage="No models match"
      />
      {hint ? <p className="field-hint">{hint}</p> : null}
    </div>
  );
}
