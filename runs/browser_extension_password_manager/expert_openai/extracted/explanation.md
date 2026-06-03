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
---

# 2. Root workspace files

## `package.json`
## `pnpm-workspace.yaml`
## `tsconfig.base.json`
---

# 3. Shared client-side crypto package

The backend never receives plaintext vault data or vault keys.

## `packages/crypto/package.json`
## `packages/crypto/src/index.ts`
## `packages/crypto/src/index.test.ts`
---

# 4. Chrome extension

## `apps/extension/package.json`
## `apps/extension/manifest.json`
## `apps/extension/vite.config.ts`
## `apps/extension/index.html`
## `apps/extension/src/types.ts`
## `apps/extension/src/auth.ts`
## `apps/extension/src/vaultClient.ts`
## `apps/extension/src/background.ts`
## `apps/extension/src/contentScript.ts`
## `apps/extension/src/popup/main.tsx`
## `apps/extension/src/popup/App.tsx`
---

# 5. Secure API service

## `apps/api/package.json`
## `apps/api/prisma/schema.prisma`
## `apps/api/src/env.ts`
## `apps/api/src/db.ts`
## `apps/api/src/audit.ts`
## `apps/api/src/risk.ts`
## `apps/api/src/auth.ts`
## `apps/api/src/routes/auth.ts`
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
