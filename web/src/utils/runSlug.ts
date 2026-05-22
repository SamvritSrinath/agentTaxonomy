/** Extract prompt artifact segment from run slug (e.g. beginner_canonical_moonshotai_kimi-k2.5). */
export function promptArtifactFromRunSlug(runSlug: string): string {
  const parts = runSlug.split("_");
  if (parts.length >= 2) {
    return `${parts[0]}_${parts[1]}`;
  }
  return runSlug;
}
