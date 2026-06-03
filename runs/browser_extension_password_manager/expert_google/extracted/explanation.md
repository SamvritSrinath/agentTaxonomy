Here is a complete, production-grade, scalable password-management ecosystem centered around a Manifest V3 Chrome Extension. 

This system is designed with a **Zero-Knowledge Architecture**: all encryption and decryption occur client-side. The server never receives the master password or the raw encryption keys. It only receives a cryptographically derived authentication hash and encrypted vault payloads.

---

### System Architecture & Cryptographic Flow
---

### Directory Structure
---

### 1. Cryptographic Workflows (Client-Side)

This module handles zero-knowledge key derivation and AES-GCM-256 encryption/decryption using the native Web Crypto API.

#### `extension/src/utils/crypto.ts`
---

### 2. Chrome Extension (Manifest V3)

#### `extension/manifest.json`
#### `extension/src/background.ts`
#### `extension/src/content.ts`
#### `extension/src/popup.tsx`
---

### 3. Secure API Services (Backend)

This Node.js/TypeScript service handles authentication, WebAuthn/Passkey registration, zero-knowledge vault synchronization, and risk-based login detection.

#### `backend/src/server.ts`
#### `backend/src/services/risk.service.ts`
#### `backend/src/controllers/auth.controller.ts`
#### `backend/src/controllers/vault.controller.ts`
#### `backend/src/middleware/audit.middleware.ts`
```typescript
import { Request, Response, NextFunction } from 'express';
import { db } from '../server';

export async function auditLogger(req: Request, res: Response, next: NextFunction) {
  const startTime = Date.now();

  res.on('finish', async () => {
    const duration = Date.now() - startTime;
    const ip = req.ip || 'unknown';
    const userAgent = req.headers['user-agent'] || 'unknown';
    const action = `${req.method} ${req.route?.path || req.path}`;
    const status = res.statusCode;

    // Extract user ID from request context if authenticated (mocked here for simplicity)
    const userId = (req as any).user?.userId || null;

    try {
      await db.query(
        `INSERT INTO audit_logs (user_id, action, ip_address, user_agent, status, duration_ms) 
         VALUES ($1, $2, $3, $4, $5, $6)`,
        [userId, action, ip, userAgent,
