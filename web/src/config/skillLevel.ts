export const SKILL_LEVEL_ORDER: Record<string, number> = {
  beginner: 0,
  intermediate: 1,
  expert: 2
};

export const SKILL_LEVELS = ["beginner", "intermediate", "expert"] as const;

export function skillLevelRank(level: string | null | undefined): number {
  if (!level) return 99;
  return SKILL_LEVEL_ORDER[level.toLowerCase()] ?? 99;
}

/** Parse skill from instance_id suffix like `task__beginner`. */
export function parseSkillFromInstanceId(instanceId: string | null | undefined): string | null {
  if (!instanceId) return null;
  const match = instanceId.match(/__(beginner|intermediate|expert)$/i);
  return match ? match[1].toLowerCase() : null;
}
