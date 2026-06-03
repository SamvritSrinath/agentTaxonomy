import { db } from "./db";

export type RiskInput = {
  userId?: string;
  ip?: string;
  userAgent?: string;
  country?: string;
};

export async function scoreLoginRisk(input: RiskInput): Promise<number> {
  let score = 0;

  if (!input.userId) score += 30;
  if (!input.ip) score += 20;
  if (!input.userAgent) score += 15;

  if (input.userId) {
    const recent = await db.auditEvent.findMany({
      where: {
        userId: input.userId,
        type: "auth.login.success",
        createdAt: {
          gte: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)
        }
      },
      orderBy: {
        createdAt: "desc"
      },
      take: 20
    });

    const knownIp = recent.some(e => e.ip === input.ip);
    const knownUa = recent.some(e => e.userAgent === input.userAgent);

    if (recent.length > 0 && !knownIp) score += 35;
    if (recent.length > 0 && !knownUa) score += 20;
  }

  return Math.min(score, 100);
}

export function isStepUpRequired(score: number): boolean {
  return score >= 60;
}
