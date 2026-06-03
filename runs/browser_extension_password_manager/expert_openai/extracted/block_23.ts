import { db } from "./db";

export async function audit(event: {
  userId?: string;
  type: string;
  ip?: string;
  userAgent?: string;
  riskScore?: number;
  metadata?: Record<string, unknown>;
}) {
  await db.auditEvent.create({
    data: {
      userId: event.userId,
      type: event.type,
      ip: event.ip,
      userAgent: event.userAgent,
      riskScore: event.riskScore,
      metadata: event.metadata ?? {}
    }
  });
}
