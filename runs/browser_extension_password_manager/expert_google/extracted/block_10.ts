import { Request, Response } from 'express';
import { db } from '../server';
import { assessLoginRisk } from '../services/risk.service';
import jwt from 'jsonwebtoken';

const JWT_SECRET = process.env.JWT_SECRET || 'super-secret-key';

export async function getSalt(req: Request, res: Response) {
  const { email } = req.query;
  if (!email) return res.status(400).json({ error: 'Email required' });

  try {
    const result = await db.query('SELECT salt FROM users WHERE email = $1', [email]);
    if (result.rowCount === 0) {
      return res.status(404).json({ error: 'User not found' });
    }
    res.json({ salt: result.rows[0].salt });
  } catch (err) {
    res.status(500).json({ error: 'Internal server error' });
  }
}

export async function register(req: Request, res: Response) {
  const { email, authHash, salt } = req.body;
  try {
    const result = await db.query(
      'INSERT INTO users (email, auth_hash, salt) VALUES ($1, $2, $3) RETURNING id',
      [email, authHash, salt]
    );
    res.status(201).json({ userId: result.rows[0].id });
  } catch (err) {
    res.status(400).json({ error: 'User already exists or invalid data' });
  }
}

export async function login(req: Request, res: Response) {
  const { email, authHash } = req.body;
  const ip = req.ip || 'unknown';
  const userAgent = req.headers['user-agent'] || 'unknown';

  try {
    const userRes = await db.query('SELECT id, auth_hash FROM users WHERE email = $1', [email]);
    if (userRes.rowCount === 0) return res.status(401).json({ error: 'Invalid credentials' });

    const user = userRes.rows[0];

    // Verify Auth Hash (Zero-Knowledge verification)
    if (user.auth_hash !== authHash) {
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    // Risk-Based Login Assessment
    const risk = await assessLoginRisk(user.id, ip, userAgent);
    if (risk.requiresStepUp) {
      return res.status(403).json({
        error: 'STEP_UP_REQUIRED',
        message: 'High-risk login detected. WebAuthn/Passkey verification required.'
      });
    }

    // Record device as known
    await db.query(
      'INSERT INTO known_devices (user_id, ip_address, user_agent) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING',
      [user.id, ip, userAgent]
    );

    // Fetch encrypted vault
    const vaultRes = await db.query('SELECT encrypted_data, iv FROM vaults WHERE user_id = $1', [user.id]);
    const vault = vaultRes.rows[0] || { encrypted_data: null, iv: null };

    const token = jwt.sign({ userId: user.id }, JWT_SECRET, { expiresIn: '1h' });

    res.json({
      token,
      encryptedVault: vault.encrypted_data,
      iv: vault.iv
    });
  } catch (err) {
    res.status(500).json({ error: 'Internal server error' });
  }
}
