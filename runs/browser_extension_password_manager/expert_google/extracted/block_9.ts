import { db } from '../server';

interface RiskAssessment {
  riskScore: number; // 0 to 100
  requiresStepUp: boolean;
}

/**
 * Evaluates login risk based on IP history, User-Agent, and time anomalies.
 */
export async function assessLoginRisk(userId: string, ip: string, userAgent: string): Promise<RiskAssessment> {
  let riskScore = 0;

  // 1. Check if IP is known
  const ipCheck = await db.query(
    'SELECT id FROM known_devices WHERE user_id = $1 AND ip_address = $2',
    [userId, ip]
  );

  if (ipCheck.rowCount === 0) {
    riskScore += 40; // New IP address
  }

  // 2. Check if User-Agent is known
  const uaCheck = await db.query(
    'SELECT id FROM known_devices WHERE user_id = $1 AND user_agent = $2',
    [userId, userAgent]
  );

  if (uaCheck.rowCount === 0) {
    riskScore += 30; // New User-Agent
  }

  // 3. Check for rapid travel (impossible travel time)
  const lastLogin = await db.query(
    'SELECT ip_address, created_at FROM audit_logs WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1',
    [userId]
  );

  if (lastLogin.rowCount > 0) {
    const lastIp = lastLogin.rows[0].ip_address;
    if (lastIp !== ip) {
      // Simple mock of geographic distance check
      riskScore += 20;
    }
  }

  return {
    riskScore,
    requiresStepUp: riskScore >= 70
  };
}
