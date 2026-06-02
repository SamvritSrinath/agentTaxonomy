Below is a secure, scalable **TypeScript/React/Manifest V3 password-manager ecosystem scaffold** with:

- Chrome extension
- Secure backend API
- Client-side encryption workflows
- WebAuthn/passkey + federated auth hooks
- Encrypted vault sync/backup
- Risk-based login detection
- Audit logging
- Kubernetes + monitoring
- Browser-extension threat-model controls

---

# 1. Repository layout

```txt
password-manager/
  package.json
  pnpm-workspace.yaml
  tsconfig.base.json

  packages/
    crypto/
      package.json
      src/index.ts
      src/index.test.ts

  apps/
    extension/
      package.json
      vite.config.ts
      index.html
      manifest.json
      src/
        background.ts
        contentScript.ts
        popup/
          App.tsx
          main.tsx
        vaultClient.ts
        auth.ts
        types.ts

    api/
      package.json
      Dockerfile
      prisma/
        schema.prisma
      src/
        server.ts
        db.ts
        env.ts
        auth.ts
        risk.ts
        audit.ts
        routes/
          auth.ts
          vault.ts
          webauthn.ts
          audit.ts
        tests/
          risk.test.ts

  infra/
    k8s/
      namespace.yaml
      api-deployment.yaml
      api-service.yaml
      postgres.yaml
      ingress.yaml
      network-policy.yaml
      service-monitor.yaml
      prometheus-rules.yaml
      sealed-secret-example.yaml
```

---

# 2. Root workspace files

## `package.json`

```json
{
  "name": "password-manager",
  "private": true,
  "packageManager": "pnpm@9.12.0",
  "scripts": {
    "build": "pnpm -r build",
    "test": "pnpm -r test",
    "lint": "pnpm -r lint"
  },
  "devDependencies": {
    "typescript": "^5.6.3",
    "vitest": "^2.1.4"
  }
}
```

## `pnpm-workspace.yaml`

```yaml
packages:
  - "apps/*"
  - "packages/*"
```

## `tsconfig.base.json`

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "esModuleInterop": true
  }
}
```

---

# 3. Shared client-side crypto package

The backend never receives plaintext vault data or vault keys.

## `packages/crypto/package.json`

```json
{
  "name": "@pm/crypto",
  "version": "0.1.0",
  "type": "module",
  "main": "src/index.ts",
  "scripts": {
    "build": "tsc --noEmit",
    "test": "vitest run",
    "lint": "tsc --noEmit"
  },
  "devDependencies": {
    "typescript": "^5.6.3",
    "vitest": "^2.1.4"
  }
}
```

## `packages/crypto/src/index.ts`

```ts
export type EncryptedPayload = {
  version: 1;
  alg: "AES-GCM-256";
  kdf: "PBKDF2-SHA256";
  iterations: number;
  saltB64: string;
  ivB64: string;
  ciphertextB64: string;
};

export type VaultRecord = {
  id: string;
  origin: string;
  username: string;
  password: string;
  notes?: string;
  updatedAt: string;
};

const enc = new TextEncoder();
const dec = new TextDecoder();

function b64(bytes: ArrayBuffer | Uint8Array): string {
  const u8 = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  let bin = "";
  for (const b of u8) bin += String.fromCharCode(b);
  return btoa(bin);
}

function fromB64(value: string): Uint8Array {
  const bin = atob(value);
  return Uint8Array.from(bin, c => c.charCodeAt(0));
}

export function randomBytes(length: number): Uint8Array {
  const out = new Uint8Array(length);
  crypto.getRandomValues(out);
  return out;
}

export async function deriveVaultKey(
  masterSecret: string,
  salt: Uint8Array,
  iterations = 600_000
): Promise<CryptoKey> {
  const baseKey = await crypto.subtle.importKey(
    "raw",
    enc.encode(masterSecret),
    "PBKDF2",
    false,
    ["deriveKey"]
  );

  return crypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      hash: "SHA-256",
      salt,
      iterations
    },
    baseKey,
    {
      name: "AES-GCM",
      length: 256
    },
    false,
    ["encrypt", "decrypt"]
  );
}

export async function encryptJson<T>(
  value: T,
  masterSecret: string
): Promise<EncryptedPayload> {
  const salt = randomBytes(32);
  const iv = randomBytes(12);
  const iterations = 600_000;
  const key = await deriveVaultKey(masterSecret, salt, iterations);

  const ciphertext = await crypto.subtle.encrypt(
    {
      name: "AES-GCM",
      iv,
      additionalData: enc.encode("pm-vault-v1")
    },
    key,
    enc.encode(JSON.stringify(value))
  );

  return {
    version: 1,
    alg: "AES-GCM-256",
    kdf: "PBKDF2-SHA256",
    iterations,
    saltB64: b64(salt),
    ivB64: b64(iv),
    ciphertextB64: b64(ciphertext)
  };
}

export async function decryptJson<T>(
  payload: EncryptedPayload,
  masterSecret: string
): Promise<T> {
  if (payload.version !== 1 || payload.alg !== "AES-GCM-256") {
    throw new Error("Unsupported vault payload");
  }

  const salt = fromB64(payload.saltB64);
  const iv = fromB64(payload.ivB64);
  const ciphertext = fromB64(payload.ciphertextB64);
  const key = await deriveVaultKey(masterSecret, salt, payload.iterations);

  const plaintext = await crypto.subtle.decrypt(
    {
      name: "AES-GCM",
      iv,
      additionalData: enc.encode("pm-vault-v1")
    },
    key,
    ciphertext
  );

  return JSON.parse(dec.decode(plaintext)) as T;
}

export function newVaultRecord(input: Omit<VaultRecord, "id" | "updatedAt">): VaultRecord {
  return {
    id: crypto.randomUUID(),
    updatedAt: new Date().toISOString(),
    ...input
  };
}
```

## `packages/crypto/src/index.test.ts`

```ts
import { describe, expect, it } from "vitest";
import { decryptJson, encryptJson, VaultRecord } from "./index";

describe("vault crypto", () => {
  it("encrypts and decrypts vault data", async () => {
    const vault: VaultRecord[] = [
      {
        id: "1",
        origin: "https://example.com",
        username: "alice",
        password: "correct-horse-battery-staple",
        updatedAt: new Date().toISOString()
      }
    ];

    const encrypted = await encryptJson(vault, "master password");
    expect(encrypted.ciphertextB64).not.toContain("correct-horse");

    const decrypted = await decryptJson<VaultRecord[]>(encrypted, "master password");
    expect(decrypted[0]?.username).toBe("alice");
  });

  it("fails on wrong master secret", async () => {
    const encrypted = await encryptJson([{ secret: "value" }], "right");
    await expect(decryptJson(encrypted, "wrong")).rejects.toThrow();
  });
});
```

---

# 4. Chrome extension

## `apps/extension/package.json`

```json
{
  "name": "@pm/extension",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "vite build",
    "test": "vitest run",
    "lint": "tsc --noEmit"
  },
  "dependencies": {
    "@pm/crypto": "workspace:*",
    "@vitejs/plugin-react": "^4.3.3",
    "vite": "^5.4.10",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@types/chrome": "^0.0.278",
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "typescript": "^5.6.3",
    "vitest": "^2.1.4"
  }
}
```

## `apps/extension/manifest.json`

```json
{
  "manifest_version": 3,
  "name": "Secure Password Manager",
  "version": "0.1.0",
  "description": "Client-side encrypted password vault with secure cloud sync.",
  "action": {
    "default_popup": "index.html",
    "default_title": "Password Manager"
  },
  "background": {
    "service_worker": "src/background.ts",
    "type": "module"
  },
  "content_scripts": [
    {
      "matches": ["https://*/*"],
      "js": ["src/contentScript.ts"],
      "run_at": "document_idle",
      "all_frames": false
    }
  ],
  "permissions": [
    "storage",
    "activeTab",
    "scripting",
    "identity"
  ],
  "host_permissions": [
    "https://api.example.com/*",
    "https://app.example.com/*"
  ],
  "externally_connectable": {
    "matches": ["https://app.example.com/*"]
  },
  "content_security_policy": {
    "extension_pages": "script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none';"
  }
}
```

## `apps/extension/vite.config.ts`

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        popup: "index.html",
        background: "src/background.ts",
        contentScript: "src/contentScript.ts"
      },
      output: {
        entryFileNames: "src/[name].js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]"
      }
    }
  }
});
```

## `apps/extension/index.html`

```html
<!doctype html>
<html>
  <head>
    <meta charset="UTF-8" />
    <title>Password Manager</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/popup/main.tsx"></script>
  </body>
</html>
```

## `apps/extension/src/types.ts`

```ts
import type { EncryptedPayload, VaultRecord } from "@pm/crypto";

export type Session = {
  accessToken: string;
  expiresAt: number;
};

export type VaultState = {
  records: VaultRecord[];
  version: number;
};

export type SyncEnvelope = {
  vaultVersion: number;
  encryptedVault: EncryptedPayload;
};

export type BackgroundRequest =
  | { type: "AUTH_LOGIN" }
  | { type: "SYNC_PULL"; masterSecret: string }
  | { type: "SYNC_PUSH"; masterSecret: string; state: VaultState }
  | { type: "FILL_CREDENTIAL"; record: VaultRecord };
```

## `apps/extension/src/auth.ts`

```ts
import type { Session } from "./types";

const API_BASE = "https://api.example.com";

export async function getSession(): Promise<Session | null> {
  const result = await chrome.storage.session.get("session");
  return (result.session as Session | undefined) ?? null;
}

export async function setSession(session: Session): Promise<void> {
  await chrome.storage.session.set({ session });
}

export async function loginWithOidcPkce(): Promise<Session> {
  const redirectUrl = chrome.identity.getRedirectURL("oidc");
  const authUrl = new URL("https://app.example.com/oauth/authorize");

  authUrl.searchParams.set("client_id", "chrome-extension");
  authUrl.searchParams.set("response_type", "code");
  authUrl.searchParams.set("redirect_uri", redirectUrl);
  authUrl.searchParams.set("scope", "openid profile email");
  authUrl.searchParams.set("state", crypto.randomUUID());

  const responseUrl = await chrome.identity.launchWebAuthFlow({
    url: authUrl.toString(),
    interactive: true
  });

  const code = new URL(responseUrl).searchParams.get("code");
  if (!code) throw new Error("Missing authorization code");

  const res = await fetch(`${API_BASE}/auth/extension-token`, {
    method: "POST",
    headers: {
      "content-type": "application/json"
    },
    credentials: "omit",
    body: JSON.stringify({
      code,
      redirectUri: redirectUrl
    })
  });

  if (!res.ok) throw new Error("Authentication failed");

  const session = (await res.json()) as Session;
  await setSession(session);
  return session;
}
```

## `apps/extension/src/vaultClient.ts`

```ts
import { decryptJson, encryptJson, VaultRecord } from "@pm/crypto";
import type { Session, SyncEnvelope, VaultState } from "./types";

const API_BASE = "https://api.example.com";

export async function pullVault(
  session: Session,
  masterSecret: string
): Promise<VaultState> {
  const res = await fetch(`${API_BASE}/vault`, {
    headers: {
      authorization: `Bearer ${session.accessToken}`
    }
  });

  if (res.status === 404) {
    return { records: [], version: 0 };
  }

  if (!res.ok) throw new Error("Failed to pull vault");

  const envelope = (await res.json()) as SyncEnvelope;
  const records = await decryptJson<VaultRecord[]>(
    envelope.encryptedVault,
    masterSecret
  );

  return {
    records,
    version: envelope.vaultVersion
  };
}

export async function pushVault(
  session: Session,
  masterSecret: string,
  state: VaultState
): Promise<VaultState> {
  const encryptedVault = await encryptJson(state.records, masterSecret);

  const res = await fetch(`${API_BASE}/vault`, {
    method: "PUT",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${session.accessToken}`,
      "if-match": String(state.version)
    },
    body: JSON.stringify({ encryptedVault })
  });

  if (res.status === 409) {
    throw new Error("Vault conflict. Pull latest and merge.");
  }

  if (!res.ok) throw new Error("Failed to push vault");

  return (await res.json()) as VaultState;
}
```

## `apps/extension/src/background.ts`

```ts
import { loginWithOidcPkce, getSession } from "./auth";
import { pullVault, pushVault } from "./vaultClient";
import type { BackgroundRequest } from "./types";

chrome.runtime.onMessage.addListener((msg: BackgroundRequest, sender, sendResponse) => {
  void handleMessage(msg, sender)
    .then(sendResponse)
    .catch(err => sendResponse({ error: err instanceof Error ? err.message : "Unknown error" }));

  return true;
});

async function handleMessage(msg: BackgroundRequest, sender: chrome.runtime.MessageSender) {
  switch (msg.type) {
    case "AUTH_LOGIN":
      return loginWithOidcPkce();

    case "SYNC_PULL": {
      const session = await requireSession();
      return pullVault(session, msg.masterSecret);
    }

    case "SYNC_PUSH": {
      const session = await requireSession();
      return pushVault(session, msg.masterSecret, msg.state);
    }

    case "FILL_CREDENTIAL": {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab.id || !tab.url?.startsWith("https://")) {
        throw new Error("Can only fill into active HTTPS tabs");
      }

      const tabOrigin = new URL(tab.url).origin;
      if (new URL(msg.record.origin).origin !== tabOrigin) {
        throw new Error("Credential origin mismatch");
      }

      await chrome.tabs.sendMessage(tab.id, {
        type: "PM_FILL",
        username: msg.record.username,
        password: msg.record.password,
        origin: msg.record.origin
      });

      return { ok: true };
    }
  }
}

async function requireSession() {
  const session = await getSession();
  if (!session || session.expiresAt < Date.now() + 30_000) {
    throw new Error("Not authenticated");
  }
  return session;
}
```

## `apps/extension/src/contentScript.ts`

```ts
type FillMessage = {
  type: "PM_FILL";
  origin: string;
  username: string;
  password: string;
};

chrome.runtime.onMessage.addListener((msg: FillMessage) => {
  if (msg.type !== "PM_FILL") return;

  if (location.origin !== new URL(msg.origin).origin) {
    return;
  }

  const passwordInput = findPasswordInput();
  if (!passwordInput) return;

  const form = passwordInput.closest("form") ?? document;
  const usernameInput = findUsernameInput(form);

  if (usernameInput) setNativeValue(usernameInput, msg.username);
  setNativeValue(passwordInput, msg.password);
});

function findPasswordInput(): HTMLInputElement | null {
  return document.querySelector<HTMLInputElement>('input[type="password"]');
}

function findUsernameInput(root: ParentNode): HTMLInputElement | null {
  return (
    root.querySelector<HTMLInputElement>('input[autocomplete="username"]') ??
    root.querySelector<HTMLInputElement>('input[type="email"]') ??
    root.querySelector<HTMLInputElement>('input[type="text"]')
  );
}

function setNativeValue(input: HTMLInputElement, value: string) {
  const descriptor = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype,
    "value"
  );

  descriptor?.set?.call(input, value);

  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}
```

## `apps/extension/src/popup/main.tsx`

```tsx
import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

createRoot(document.getElementById("root")!).render(<App />);
```

## `apps/extension/src/popup/App.tsx`

```tsx
import React, { useState } from "react";
import { newVaultRecord, VaultRecord } from "@pm/crypto";
import type { VaultState } from "../types";

export function App() {
  const [masterSecret, setMasterSecret] = useState("");
  const [vault, setVault] = useState<VaultState>({ records: [], version: 0 });
  const [status, setStatus] = useState("");

  async function send<T>(message: unknown): Promise<T> {
    const response = await chrome.runtime.sendMessage(message);
    if (response?.error) throw new Error(response.error);
    return response as T;
  }

  async function login() {
    setStatus("Authenticating...");
    await send({ type: "AUTH_LOGIN" });
    setStatus("Authenticated");
  }

  async function pull() {
    setStatus("Pulling vault...");
    const state = await send<VaultState>({ type: "SYNC_PULL", masterSecret });
    setVault(state);
    setStatus(`Loaded ${state.records.length} records`);
  }

  async function push(state = vault) {
    setStatus("Syncing vault...");
    const next = await send<VaultState>({
      type: "SYNC_PUSH",
      masterSecret,
      state
    });
    setVault(next);
    setStatus("Synced");
  }

  async function addDemoRecord() {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const origin = tab.url ? new URL(tab.url).origin : "https://example.com";

    const record = newVaultRecord({
      origin,
      username: "user@example.com",
      password: crypto.randomUUID() + crypto.randomUUID()
    });

    const next = {
      records: [...vault.records, record],
      version: vault.version
    };

    setVault(next);
    await push(next);
  }

  async function fill(record: VaultRecord) {
    await send({ type: "FILL_CREDENTIAL", record });
    setStatus("Filled");
  }

  return (
    <main style={{ width: 360, padding: 16, fontFamily: "system-ui" }}>
      <h2>Password Manager</h2>

      <button onClick={login}>Federated Login</button>

      <div style={{ marginTop: 12 }}>
        <input
          type="password"
          placeholder="Master secret"
          value={masterSecret}
          onChange={e => setMasterSecret(e.target.value)}
          style={{ width: "100%" }}
        />
      </div>

      <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
        <button disabled={!masterSecret} onClick={pull}>Pull</button>
        <button disabled={!masterSecret} onClick={() => push()}>Push</button>
        <button disabled={!masterSecret} onClick={addDemoRecord}>Add</button>
      </div>

      <p>{status}</p>

      <ul>
        {vault.records.map(record => (
          <li key={record.id}>
            <b>{record.origin}</b>
            <br />
            {record.username}
            <br />
            <button onClick={() => fill(record)}>Fill</button>
          </li>
        ))}
      </ul>
    </main>
  );
}
```

---

# 5. Secure API service

## `apps/api/package.json`

```json
{
  "name": "@pm/api",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "tsx watch src/server.ts",
    "build": "tsc --noEmit",
    "start": "node dist/server.js",
    "test": "vitest run",
    "lint": "tsc --noEmit",
    "prisma:generate": "prisma generate",
    "prisma:migrate": "prisma migrate deploy"
  },
  "dependencies": {
    "@fastify/cors": "^10.0.1",
    "@fastify/helmet": "^12.0.1",
    "@fastify/jwt": "^9.0.1",
    "@fastify/rate-limit": "^10.1.0",
    "@fastify/sensible": "^6.0.1",
    "@fastify/swagger": "^9.2.0",
    "@prisma/client": "^5.21.1",
    "@simplewebauthn/server": "^10.0.0",
    "fastify": "^5.0.0",
    "jose": "^5.9.6",
    "prom-client": "^15.1.3",
    "prisma": "^5.21.1",
    "zod": "^3.23.8"
  },
  "devDependencies": {
    "@types/node": "^22.8.4",
    "tsx": "^4.19.2",
    "typescript": "^5.6.3",
    "vitest": "^2.1.4"
  }
}
```

## `apps/api/prisma/schema.prisma`

```prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id                 String               @id @default(uuid())
  email              String               @unique
  createdAt          DateTime             @default(now())
  updatedAt          DateTime             @updatedAt
  vault              Vault?
  credentials        WebAuthnCredential[]
  auditEvents        AuditEvent[]
}

model Vault {
  id             String   @id @default(uuid())
  userId         String   @unique
  version        Int      @default(1)
  encryptedVault Json
  createdAt      DateTime @default(now())
  updatedAt      DateTime @updatedAt

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)
}

model WebAuthnCredential {
  id              String   @id @default(uuid())
  userId          String
  credentialId    String   @unique
  publicKey       Bytes
  counter         BigInt
  transports      String[]
  createdAt       DateTime @default(now())

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)
}

model AuditEvent {
  id          String   @id @default(uuid())
  userId      String?
  type        String
  ip          String?
  userAgent   String?
  riskScore   Int?
  metadata    Json
  createdAt   DateTime @default(now())

  user User? @relation(fields: [userId], references: [id], onDelete: SetNull)

  @@index([userId, createdAt])
  @@index([type, createdAt])
}
```

## `apps/api/src/env.ts`

```ts
import { z } from "zod";

const schema = z.object({
  NODE_ENV: z.string().default("development"),
  PORT: z.coerce.number().default(8080),
  DATABASE_URL: z.string().url(),
  JWT_SECRET: z.string().min(32),
  OIDC_ISSUER: z.string().url(),
  OIDC_AUDIENCE: z.string().min(1),
  RP_ID: z.string().default("app.example.com"),
  RP_ORIGIN: z.string().url().default("https://app.example.com")
});

export const env = schema.parse(process.env);
```

## `apps/api/src/db.ts`

```ts
import { PrismaClient } from "@prisma/client";

export const db = new PrismaClient({
  log: ["warn", "error"]
});
```

## `apps/api/src/audit.ts`

```ts
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
```

## `apps/api/src/risk.ts`

```ts
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
```

## `apps/api/src/auth.ts`

```ts
import type { FastifyRequest } from "fastify";

export type AuthUser = {
  sub: string;
  email: string;
};

export async function requireUser(request: FastifyRequest): Promise<AuthUser> {
  await request.jwtVerify();

  const user = request.user as {
    sub?: string;
    email?: string;
  };

  if (!user.sub || !user.email) {
    throw request.server.httpErrors.unauthorized("Invalid token");
  }

  return {
    sub: user.sub,
    email: user.email
  };
}
```

## `apps/api/src/routes/auth.ts`

```ts
import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { db } from "../db";
import { audit } from "../audit";
import { scoreLoginRisk, isStepUpRequired } from "../risk";

const extensionTokenSchema = z.object({
  code: z.string().min(8),
  redirectUri: z.string().url()
});

export async function authRoutes(app: FastifyInstance) {
  app.post("/auth/extension-token", async (request, reply) => {
    const body = extensionTokenSchema.parse(request.body);

    /*
      Production implementation:
      1. Exchange authorization code with OIDC provider using PKCE.
      2. Validate ID token issuer/audience/nonce with jose.
      3. Extract verified subject/email.
      4. Enforce passkey step-up when risk is high.

      This scaffold simulates a verified identity for local integration.
    */

    const email = "user@example.com";
    const oidcSub = `oidc:${email}`;

    const user = await db.user.upsert({
      where: { email },
      update: {},
      create: { email }
    });

    const riskScore = await scoreLoginRisk({
      userId: user.id,
      ip: request.ip,
      userAgent: request.headers["user-agent"]
    });

    await audit({
      userId: user.id,
      type: "auth.login.success",
      ip: request.ip,
      userAgent: request.headers["user-agent"],
      riskScore,
      metadata: {
        oidcSub,
        redirectUri: body.redirectUri,
        stepUpRequired: isStepUpRequired(riskScore)
      }
    });

    const accessToken = app.jwt.sign(
      {
        sub: user.id,
        email: user.email,
        acr: isStepUpRequired(riskScore) ? "urn:pm:step-up-required" : "urn:pm:normal"
      },
      {
        expiresIn: "15m"
      }
    );

    return reply.send({
      accessToken,
      expiresAt: Date.now() + 15 * 60 * 1000,
      stepUpRequired: isStepUpRequired(riskScore)
    });
  });
}
```

## `apps/api/src/routes/vault.ts`

```ts
import type { FastifyInstance } from "fastify";
import { z } from "zod";
import { requireUser } from "../auth";
import { db } from "../db";
import { audit } from "../audit";

const encryptedPayloadSchema = z.object({
  version: z.literal(1),
  alg: z.literal("AES-GCM-256"),
  kdf: z.literal("PBKDF2-SHA256"),
  iterations: z.number().int().min(300_000),
  saltB64: z.string().min(16),
  ivB64: z.string().min(12),
  ciphertextB64: z.string().min(16)
});

const putVaultSchema = z.object({
  encryptedVault: encryptedPayloadSchema
});

export async function vaultRoutes(app: FastifyInstance) {
  app.get("/vault", async (request, reply) => {
    const user = await requireUser(request);

    const vault = await db.vault.findUnique({
      where: {
        userId: user.sub
      }
    });

    await audit({
      userId: user.sub,
      type: "vault.read",
      ip: request.ip,
      userAgent: request.headers["user-agent"]
    });

    if (!vault) {
      return reply.code(404).send({ error: "No vault" });
    }

    return reply.send({
      vaultVersion: vault.version,
      encryptedVault: vault.encryptedVault
    });
  });

  app.put("/vault", async (request, reply) => {
    const user = await requireUser(request);
    const body = putVaultSchema.parse(request.body);

    const ifMatchRaw = request.headers["if-match"];
    const ifMatch = typeof ifMatchRaw === "string" ? Number(ifMatchRaw) : undefined;

    if (ifMatch === undefined || Number.isNaN(ifMatch)) {
      throw app.httpErrors.preconditionRequired("Missing If-Match vault version");
    }

    const existing = await db.vault.findUnique({
      where: {
        userId: user.sub
      }
    });

    if (!existing) {
      if (ifMatch !== 0) {
        throw app.httpErrors.conflict("Vault version conflict");
      }

      const created = await db.vault.create({
        data: {
          userId: user.sub,
          version: 1,
          encryptedVault: body.encryptedVault
        }
      });

      await audit({
        userId: user.sub,
        type: "vault.create",
        ip: request.ip,
        userAgent: request.headers["user-agent"]
      });

      return reply.send({
        records: [],
        version: created.version
      });
    }

    if (existing.version !== ifMatch) {
      throw app.httpErrors.conflict("Vault version conflict");
    }

    const updated = await db.vault.update({
      where: {
        userId: user.sub
      },
      data: {
       
