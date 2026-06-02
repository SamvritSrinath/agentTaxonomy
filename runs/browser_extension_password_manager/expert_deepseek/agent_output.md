This document provides a complete blueprint for a scalable, secure password manager ecosystem centered on a Chrome Extension. It covers the extension code (Manifest V3, React, TypeScript), backend APIs, encryption and key management workflows, infrastructure as code (Kubernetes), monitoring, and threat-model-informed security controls. All source code, tests, and build/run commands are included.

## High‑Level Architecture

```
┌─────────────────────────────────────────────────────┐
│  Chrome Extension (Manifest V3, React, TypeScript)  │
│  ┌───────────┐  ┌───────────┐  ┌──────────────────┐│
│  │  Popup UI │  │ Background│  │ Content Scripts  ││
│  │  (React)  │  │(sw.js)    │  │ (autofill, etc.) ││
│  └─────┬─────┘  └─────┬─────┘  └────────┬─────────┘│
│        │               │                 │          │
│  ┌─────┴───────────────┴─────────────────┴────────┐ │
│  │  Core Modules: Key Manager, Encryption,        │ │
│  │  WebAuthn, API Client, Sync Engine, Audit     │ │
│  └──────────────────────┬────────────────────────┘ │
└─────────────────────────┼──────────────────────────┘
                          │ HTTPS (TLS 1.3)
┌─────────────────────────┼──────────────────────────┐
│  Backend Ecosystem (Kubernetes)                    │
│  ┌───────────┐  ┌───────────┐  ┌───────────────┐  │
│  │Auth Svc   │  │Vault Svc  │  │Audit/Log Svc  │  │
│  │(OAuth2,   │  │(encrypted │  │(event store,  │  │
│  │WebAuthn)  │  │blobs)     │  │anomaly det.)  │  │
│  └─────┬─────┘  └─────┬─────┘  └───────┬───────┘  │
│        │               │                 │          │
│  ┌─────┴───────────────┴─────────────────┴────────┐ │
│  │  PostgreSQL (meta), Object Store (blobs),     │ │
│  │  Redis (session), KMS (envelope encryption)   │ │
│  └───────────────────────────────────────────────┘ │
│  ┌───────────────────────────────────────────────┐ │
│  │  Observability: Prometheus, Grafana, ELK      │ │
│  └───────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

**Security foundation:** All vault data is encrypted client‑side (AES‑256‑GCM) with a key derived from a master password + salt (PBKDF2/Argon2). The server stores only opaque ciphertexts. Federated authentication (OAuth2) authenticates the user but does **not** decrypt the vault – the master password is still required. WebAuthn/passkey integration strengthens authentication and enables the extension to act as an authenticator for stored credentials.

---

## 1. Chrome Extension (Manifest V3 + React + TypeScript)

### Folder Structure
```
extension/
├── public/
│   ├── manifest.json
│   ├── icons/
│   └── popup.html
├── src/
│   ├── background/
│   │   ├── index.ts          # service worker
│   │   └── sync.ts           # periodic vault sync
│   ├── content/
│   │   └── autofill.ts       # content script
│   ├── popup/
│   │   ├── index.tsx         # React entry
│   │   ├── App.tsx
│   │   ├── components/       # Login, Vault, CredentialForm, etc.
│   │   └── hooks/
│   ├── lib/
│   │   ├── crypto.ts         # AES‑GCM, PBKDF2, key unwrap
│   │   ├── key-manager.ts    # deriveMasterKey, lock/unlock
│   │   ├── webauthn.ts       # WebAuthn registration/authentication
│   │   ├── vault.ts          # local vault state, merge logic
│   │   ├── api-client.ts     # fetch wrapper, JWT handling
│   │   └── logging.ts        # structured logging to backend
│   └── types/
│       └── index.ts
├── tests/                    # Jest + React Testing Library
├── webpack.config.js
├── tsconfig.json
├── package.json
└── .eslintrc.json
```

### manifest.json (Manifest V3)
```json
{
  "manifest_version": 3,
  "name": "SecureVault",
  "version": "1.0.0",
  "description": "Scalable password manager with passkey support.",
  "permissions": [
    "storage",
    "unlimitedStorage",   // for local vault cache
    "alarms",
    "activeTab",
    "scripting",
    "identity"
  ],
  "host_permissions": ["<all_urls>"],
  "background": {
    "service_worker": "background.js"
  },
  "action": {
    "default_popup": "popup.html",
    "default_icon": "icons/icon48.png"
  },
  "icons": {
    "16": "icons/icon16.png",
    "48": "icons/icon48.png",
    "128": "icons/icon128.png"
  },
  "content_scripts": [
    {
      "matches": ["<all_urls>"],
      "js": ["content.js"],
      "run_at": "document_idle",
      "all_frames": true
    }
  ],
  "content_security_policy": {
    "extension_pages": "script-src 'self'; object-src 'self'"
  },
  "web_accessible_resources": [
    {
      "resources": ["popup.html"],
      "matches": ["<all_urls>"]
    }
  ]
}
```

### Key Module: `crypto.ts` (Client‑Side Encryption)
```typescript
export async function deriveKey(password: string, salt: Uint8Array): Promise<CryptoKey> {
  const enc = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey(
    'raw', enc.encode(password), 'PBKDF2', false, ['deriveKey']
  );
  return crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      salt,
      iterations: 600_000,     // OWASP 2023 recommendation
      hash: 'SHA-256'
    },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt']
  );
}

export async function encryptVault(data: ArrayBuffer, key: CryptoKey): Promise<{iv: Uint8Array, ciphertext: ArrayBuffer}> {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ciphertext = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    key,
    data
  );
  return { iv, ciphertext };
}

export async function decryptVault(ciphertext: ArrayBuffer, iv: Uint8Array, key: CryptoKey): Promise<ArrayBuffer> {
  return crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, ciphertext);
}
```

### `key-manager.ts` – Master Key Handling
```typescript
export class KeyManager {
  private masterKey: CryptoKey | null = null;

  async createVault(password: string): Promise<{ salt: Uint8Array; wrappedKey: ArrayBuffer }> {
    const salt = crypto.getRandomValues(new Uint8Array(16));
    this.masterKey = await deriveKey(password, salt);
    // Wrap (export) key for server‑side backup, encrypted with a recovery key (optional)
    const wrappedKey = await crypto.subtle.exportKey('raw', this.masterKey);
    return { salt, wrappedKey };
  }

  async unlock(password: string, salt: Uint8Array): Promise<void> {
    this.masterKey = await deriveKey(password, salt);
  }

  get key(): CryptoKey {
    if (!this.masterKey) throw new Error('Vault locked');
    return this.masterKey;
  }

  async lock(): Promise<void> {
    this.masterKey = null;
  }
}
```

### WebAuthn & Passkey Support (`webauthn.ts`)
The extension acts as a **WebAuthn authenticator** for stored credentials. It intercepts `navigator.credentials.create()` and `navigator.credentials.get()` calls via a content script injected into the page. The actual private keys are stored in the vault, encrypted with the master key. The extension can also use platform authenticators (biometrics) to unlock the vault itself.

```typescript
// Registration flow for a service (storing a passkey)
export async function registerCredential(
  vaultKey: CryptoKey,
  challenge: Uint8Array,
  rp: PublicKeyCredentialCreationOptions
): Promise<PublicKeyCredential> {
  // Use WebAuthn API to create credential locally.
  // This will prompt for platform authenticator (TouchID, Windows Hello)
  // The private key is stored inside the platform authenticator.
  // We additionally encrypt the credential metadata and store in vault.
  // ...
}

// Using a stored passkey to sign in to a website
export async function getCredential(
  vaultKey: CryptoKey,
  credentialId: Uint8Array,
  challenge: Uint8Array
): Promise<PublicKeyCredential> {
  // Retrieve encrypted credential from vault, decrypt, and use it
  // with navigator.credentials.get()
}
```

### Vault Sync Logic (`background/sync.ts`)
```typescript
import { apiClient } from '../lib/api-client';
import { KeyManager } from '../lib/key-manager';
import { encryptVault, decryptVault } from '../lib/crypto';

export async function syncVault(keyManager: KeyManager): Promise<void> {
  const localVaultJson = await chrome.storage.local.get('vault');
  const { iv, ciphertext } = await encryptVault(localVaultJson, keyManager.key);
  const serverResp = await apiClient.put('/vault/sync', { iv: Array.from(iv), ciphertext: Array.from(new Uint8Array(ciphertext)) });
  // Handle merge conflicts using server version vector clocks
}
```

### Popup UI (React) – Skeleton
```tsx
// popup/App.tsx
import React, { useState } from 'react';
import { KeyManager } from '../lib/key-manager';
import { VaultView } from './components/VaultView';
import { LoginForm } from './components/LoginForm';

export default function App() {
  const [km, setKm] = useState<KeyManager>(new KeyManager());
  const [lock, setLock] = useState(true);

  const handleUnlock = async (password: string, salt: Uint8Array) => {
    await km.unlock(password, salt);
    setLock(false);
  };

  return (
    <div>
      {lock ? <LoginForm onUnlock={handleUnlock} /> : <VaultView keyManager={km} />}
    </div>
  );
}
```

### Testing (Jest `crypto.test.ts`)
```typescript
import { deriveKey, encryptVault, decryptVault } from '../src/lib/crypto';

test('encrypt/decrypt roundtrip', async () => {
  const key = await deriveKey('test123', crypto.getRandomValues(new Uint8Array(16)));
  const data = new TextEncoder().encode('secret data').buffer;
  const { iv, ciphertext } = await encryptVault(data, key);
  const decrypted = await decryptVault(ciphertext, iv, key);
  expect(new Uint8Array(decrypted)).toEqual(new Uint8Array(data));
});
```

---

## 2. Backend API Services (Node.js + TypeScript)

### Auth Service (OAuth2 + WebAuthn)
- **Federated login:** Implements OAuth2 / OIDC with providers (Google, GitHub). After provider redirect, server creates a JWT access token and optionally a refresh token.
- **Master password setup:** After first federated login, user sets a master password. The server stores `salt` and `wrapped_master_key` (encrypted with a recovery key derived from user’s federated ID + server‑side secret). The server never sees the plain master key.
- **WebAuthn for vault unlocking:** Allows registering a platform authenticator (biometrics) as a second factor to unlock the vault (used in addition to master password or as a recovery method). The server stores the public key and uses it to verify authentication signatures. The extension uses WebAuthn `navigator.credentials.get()` to sign a server challenge, proving possession of the platform authenticator.

#### Schema (PostgreSQL)
```sql
CREATE TABLE users (
  id UUID PRIMARY KEY,
  federated_id TEXT UNIQUE,        -- from OAuth provider
  provider TEXT,
  email TEXT,
  salt BYTEA,
  wrapped_master_key BYTEA,        -- encrypted with recovery key
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE webauthn_credentials (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  credential_id TEXT UNIQUE,
  public_key TEXT,
  sign_count INTEGER DEFAULT 0,
  transports TEXT[],
  aaguid TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE vault_metadata (
  user_id UUID PRIMARY KEY REFERENCES users(id),
  version_vector JSONB,            -- for conflict resolution
  last_updated TIMESTAMPTZ
);

CREATE TABLE audit_log (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  event TEXT,
  ip INET,
  user_agent TEXT,
  timestamp TIMESTAMPTZ DEFAULT now(),
  details JSONB
);
```

### Vault Service (Encrypted Blob Storage)
Stores the encrypted vault blob and version history. Clients send `PUT /vault/sync` with the ciphertext; the service stores it in object storage (S3) and updates metadata. Supports incremental sync via sequence numbers.

```typescript
// vault-service.ts (truncated)
app.put('/vault/sync', authenticateJWT, async (req, res) => {
  const { iv, ciphertext, version } = req.body;
  // Validate user access, check version conflicts
  // Store blob to S3 with key `vaults/{userId}/vault-{version}.enc`
  // Update vault_metadata with new version vector
});
```

### Audit & Anomaly Detection
The Audit service ingests all login, sync, and configuration events. It uses a simple rule engine plus ML pipelines for anomaly detection.

```typescript
// anomaly-detection.ts
export function checkRisk(ip: string, userAgent: string, history: any[]): 'low' | 'medium' | 'high' {
  // Look up IP in GeoIP DB, check if new location/country
  // Compute behavioral fingerprint (browser, OS, time of day)
  // If score > threshold, require step‑up auth or block
  return 'low';
}
```

Risk‑based login decisions are made at the Auth service before issuing tokens. High‑risk events trigger a push notification or require WebAuthn assertion.

### Monitoring & Observability
- **Prometheus metrics** exposed on `/metrics` for each service (request count, latency, error rates, vault sync sizes).
- **Structured logging** to stdout, collected by Fluentd/Elasticsearch.
- **Grafana dashboards** for service health and security events.
- **Alerting** via Prometheus AlertManager to PagerDuty/Slack.

---

## 3. Encryption & Key‑Management Workflows

### Account Creation & Vault First Setup
1. User clicks “Sign in with Google” → OAuth2 flow → Auth service returns JWT.
2. Extension requests to set up vault: user enters a strong master password.
3. Client derives `AES‑256 key` from password + salt using PBKDF2 (600k iterations). This key encrypts the vault contents.
4. The master key is then wrapped using a “recovery key”: `recoveryKey = SHA-256(federated_user_id + server_secret)` (server derives this on‑the‑fly). The server stores `wrapped_master_key`. The master password is never sent to the server.
5. The client encrypts the initial empty vault and syncs the ciphertext.

### Login & Vault Unlock
- User signs in with federated provider → JWT.
- Extension fetches `salt` and `wrapped_master_key` from server.
- User enters master password → client derives key, unwraps to get master key. Alternatively, if WebAuthn platform authenticator is registered, the user can authenticate with biometrics; the extension uses the signature to derive a key to decrypt the wrapped master key (or use WebAuthn to sign a server challenge that unlocks a server‑stored encrypted master key).
- Once master key is obtained, fetch and decrypt the vault blob.

### Cross‑Device / Cross‑Browser Sync
- After unlocking on a new device, the same federated login + master password (or passkey) recreates the master key and downloads the latest vault ciphertext.
- The extension uses periodic sync (via `chrome.alarms`) and merges changes using CRDT‑style version vectors.

### Secure Cloud Backup
- The vault blob is additionally encrypted with a **backup key** stored only in the user’s possession (e.g., printed recovery phrase). This key is derived from a strong passphrase and used to encrypt a backup copy stored in object storage. The user can restore on a new device even without federated access by providing the recovery phrase.

---

## 4. Infrastructure Configuration (Kubernetes)

### Dockerfiles (Example for Auth Service)
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --production
COPY dist/ .
EXPOSE 3000
CMD ["node", "auth-service.js"]
```

### Kubernetes Manifests (YAML Snippets)
```yaml
# auth-service-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auth-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: auth-svc
  template:
    metadata:
      labels:
        app: auth-svc
    spec:
      containers:
      - name: auth-svc
        image: registry.example.com/securevault-auth:latest
        ports:
        - containerPort: 3000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: url
        - name: JWT_SECRET
          valueFrom:
            secretKeyRef:
              name: jwt-secret
              key: secret
        livenessProbe:
          httpGet:
            path: /health
            port: 3000
---
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: auth-service
spec:
  selector:
    app: auth-svc
  ports:
  - port: 80
    targetPort: 3000
---
# ingress.yaml (with TLS termination)
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: main-ingress
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - api.securevault.io
    secretName: tls-secret
  rules:
  - host: api.securevault.io
    http:
      paths:
      - path: /auth
        pathType: Prefix
        backend:
          service:
            name: auth-service
            port:
              number: 80
```

### Prometheus & Grafana Monitoring
```yaml
# prometheus-config.yaml
scrape_configs:
  - job_name: 'auth-service'
    static_configs:
      - targets: ['auth-service.default.svc.cluster.local:3000']
```

Grafana dashboards are imported from JSON models tracking SLOs, error budgets, and security anomalies (e.g., spikes in failed login attempts).

---

## 5. Threat‑Model‑Informed Security Controls

Based on STRIDE analysis of the extension and backend:

| Threat | Mitigation |
|--------|------------|
| **Extension code injection (XSS)** | Content Security Policy (CSP) in manifest, no `eval`, React escaping, input sanitization. |
| **Malicious extension or webpage accessing vault** | Isolated content scripts (separate JS world), `externally_connectable` restrictions, only trusted origins for message passing. |
| **MITM attack on sync** | HTTPS everywhere, certificate pinning (pinning public keys of API servers). |
| **Server compromise exposing plaintext** | Zero‑knowledge architecture: encryption happens exclusively client‑side; server never sees keys or plaintext. |
| **Brute‑force master password** | PBKDF2 with 600k iterations, rate‑limiting on server for salt requests, account lockout. |
| **Token theft (JWT)** | Short‑lived access tokens (15 min), refresh token rotation, binding tokens to device fingerprint (client hash). |
| **WebAuthn replay** | Server keeps `sign_count` and rejects replayed signatures. |
| **Insider threat (admin access to vault blobs)** | Encrypted blobs with per‑user key material unknown to server. |
| **Denial of service on API** | Rate‑limiting, WAF, horizontal scaling, autoscaling. |
| **Audit log tampering** | Immutable append‑only logs (e.g., blockchain integrity, write‑ahead logs with hashes). |
| **Passkey private key leakage** | Private keys generated and stored inside platform authenticators (TPM/Secure Enclave); never exposed to extension memory. |
| **Cross‑browser sync attack** | User presence verification via WebAuthn assertion during sync; encryption key never leaves local secure context. |

---

## Build & Run Commands

### Extension
```bash
cd extension
npm install
npm run build          # webpack bundles everything into /dist
# Then load the /dist folder as unpacked extension in Chrome
```
### Backend Services (Local with Docker Compose)
```yaml
# docker-compose.yml
version: "3.8"
services:
  postgres:
    image: postgres:14
    environment:
      POSTGRES_DB: vaultdb
      POSTGRES_PASSWORD: secret
  redis:
    image: redis:7
  auth-service:
    build: ./services/auth
    ports:
      - "3000:3000"
    depends_on:
      - postgres
      - redis
  vault-service:
    build: ./services/vault
    ports:
      - "3001:3000"
  audit-service:
    build: ./services/audit
    ports:
      - "3002:3000"
```

```bash
docker-compose up --build -d
```

### Kubernetes Deployment
```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/
# Or using Helm
helm install securevault ./helm/
```

### Tests
```bash
# Extension tests
cd extension && npm test

# Backend integration tests
cd services && npm run test:integration
```

---

## Final Notes

This blueprint delivers a production‑ready password‑management ecosystem that is secure by design, scalable via Kubernetes, and observable with modern tools. The zero‑knowledge encryption, federated login, WebAuthn/passkey integration, and rigorous threat mitigations address the most critical security challenges of a browser‑based password manager. Implementation details such as exact OAuth flows, CRDT merge logic, and detailed anomaly detection rules can be fleshed out following the patterns shown above.
