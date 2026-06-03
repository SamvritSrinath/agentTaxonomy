import { Request, Response } from 'express';
import { db } from '../server';
import jwt from 'jsonwebtoken';

const JWT_SECRET = process.env.JWT_SECRET || 'super-secret-key';

export async function syncVault(req: Request, res: Response) {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Unauthorized' });
  }

  const token = authHeader.split(' ')[1];

  try {
    const decoded = jwt.verify(token, JWT_SECRET) as { userId: string };
    const { encryptedVault, iv } = req.body;

    await db.query(
      `INSERT INTO vaults (user_id, encrypted_data, iv, updated_at) 
       VALUES ($1, $2, $3, NOW()) 
       ON CONFLICT (user_id) 
       DO UPDATE SET encrypted_data = EXCLUDED.encrypted_data, iv = EXCLUDED.iv, updated_at = NOW()`,
      [decoded.userId, encryptedVault, iv]
    );

    res.json({ success: true });
  } catch (err) {
    res.status(401).json({ error: 'Invalid token' });
  }
}
