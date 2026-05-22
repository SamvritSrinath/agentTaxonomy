import type { PromptVariant } from "../api/types";
import { skillLevelRank } from "../config/skillLevel";

/** DB rows that mirror on-disk catalog prompts (bootstrap shadows). Not shown in the tree. */
export function isCatalogShadowPrompt(prompt: PromptVariant): boolean {
  if (prompt.variant_name === "canonical") {
    return true;
  }
  if (prompt.variant_name === prompt.instance_id) {
    return true;
  }
  const skill = prompt.skill_level ?? "";
  if (skill && prompt.variant_name === `${prompt.instance_id}__${skill}`) {
    return true;
  }
  return false;
}

/** Custom experiment variants only (excludes catalog shadows). */
export function experimentalPromptVariants(prompts: PromptVariant[]): PromptVariant[] {
  return prompts.filter((p) => !isCatalogShadowPrompt(p));
}

/** Display label for a custom DB variant (catalog is labeled by skill level in the tree). */
export function promptDisplayLabel(prompt: PromptVariant): string {
  return prompt.variant_name;
}

export function promptSearchText(prompt: PromptVariant): string {
  const label = promptDisplayLabel(prompt);
  const taskSlug = prompt.instance_id.split("__")[0] ?? prompt.instance_id;
  return `${label} ${taskSlug} ${prompt.instance_id} ${prompt.skill_level}`;
}

export function sortPromptVariants(prompts: PromptVariant[]): PromptVariant[] {
  return experimentalPromptVariants(prompts).sort((a, b) => {
    const skillDiff = skillLevelRank(a.skill_level) - skillLevelRank(b.skill_level);
    if (skillDiff !== 0) return skillDiff;
    return a.variant_name.localeCompare(b.variant_name);
  });
}
