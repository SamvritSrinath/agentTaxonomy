Below is a production-style Manifest V3 Chrome extension password manager implemented in TypeScript.

It includes:

- Secure local vault storage using `chrome.storage.local`
- AES-256-GCM encryption via WebCrypto
- PBKDF2 master-password key derivation
- Master password setup/unlock/lock flow
- User-triggered autofill for detected login forms
- Strict message validation and origin checks
- No `innerHTML`, no remote code, strict CSP
- Tests for crypto behavior

---

## Project structure

```text
chrome-password-manager/
  manifest.json
  package.json
  tsconfig.json
  popup.html
  styles.css
  scripts/
    copy-static.mjs
  src/
    background.ts
    content.ts
    crypto.ts
    popup.ts
    storage.ts
    types.ts
  test/
    crypto.test.ts
```

---

## `package.json`

```json
{
  "name": "secure-local-password-manager-extension",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "clean": "rimraf dist",
    "build": "npm run clean && tsc && node scripts/copy-static.mjs",
    "test": "vitest run",
    "dev:test": "vitest"
  },
  "devDependencies": {
    "@types/chrome": "^0.0.268",
    "@types/node": "^22.5.4",
    "rimraf": "^6.0.1",
    "typescript": "^5.6.2",
    "vitest": "^2.1.1"
  }
}
```

---

## `tsconfig.json`

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ES2022",
    "moduleResolution": "Bundler",
    "lib": ["ES2022", "DOM"],
    "types": ["chrome"],
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "rootDir": "src",
    "outDir": "dist",
    "sourceMap": false
  },
  "include": ["src/**/*.ts"]
}
```

---

## `manifest.json`

```json
{
  "manifest_version": 3,
  "name": "Secure Local Password Manager",
  "version": "1.0.0",
  "description": "A local-only encrypted password manager with master password login and user-triggered autofill.",
  "minimum_chrome_version": "114",
  "permissions": ["storage", "activeTab"],
  "host_permissions": ["https://*/*", "http://localhost/*", "http://127.0.0.1/*"],
  "action": {
    "default_popup": "popup.html",
    "default_title": "Password Manager"
  },
  "background": {
    "service_worker": "background.js",
    "type": "module"
  },
  "content_scripts": [
    {
      "matches": ["https://*/*", "http://localhost/*", "http://127.0.0.1/*"],
      "js": ["content.js"],
      "run_at": "document_idle",
      "all_frames": false
    }
  ],
  "content_security_policy": {
    "extension_pages": "script-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
  }
}
```

---

## `scripts/copy-static.mjs`

```js
import { copyFileSync, mkdirSync } from "node:fs";

mkdirSync("dist", { recursive: true });

copyFileSync("manifest.json", "dist/manifest.json");
copyFileSync("popup.html", "dist/popup.html");
copyFileSync("styles.css", "dist/styles.css");
```

---

## `src/types.ts`

```ts
export interface VaultEntry {
  id: string;
  origin: string;
  username: string;
  password: string;
  label: string;
  createdAt: number;
  updatedAt: number;
}

export interface PublicVaultEntry {
  id: string;
  origin: string;
  username: string;
  label: string;
  updatedAt: number;
}

export interface Vault {
  version: 1;
  entries: VaultEntry[];
}

export interface VaultEnvelope {
  version: 1;
  kdf: {
    name: "PBKDF2";
    hash: "SHA-256";
    iterations: number;
    salt: string;
  };
  cipher: {
    alg: "AES-GCM";
    iv: string;
    data: string;
  };
  createdAt: number;
  updatedAt: number;
}

export interface ApiResponse<T = unknown> {
  ok: boolean;
  data?: T;
  error?: string;
}
```

---

## `src/crypto.ts`

```ts
import type { Vault, VaultEnvelope } from "./types";

const KDF_ITERATIONS = 310_000;
const SALT_BYTES = 16;
const IV_BYTES = 12;

function subtle(): SubtleCrypto {
  if (!globalThis.crypto?.subtle) {
    throw new Error("WebCrypto is unavailable");
  }

  return globalThis.crypto.subtle;
}

export function randomBytes(length: number): Uint8Array {
  const bytes = new Uint8Array(length);
  globalThis.crypto.getRandomValues(bytes);
  return bytes;
}

export function bytesToBase64(bytes: Uint8Array): string {
  const maybeBuffer = (globalThis as unknown as { Buffer?: typeof Buffer }).Buffer;

  if (maybeBuffer) {
    return maybeBuffer.from(bytes).toString("base64");
  }

  let binary = "";
  const chunkSize = 0x8000;

  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...chunk);
  }

  return btoa(binary);
}

export function base64ToBytes(base64: string): Uint8Array {
  const maybeBuffer = (globalThis as unknown as { Buffer?: typeof Buffer }).Buffer;

  if (maybeBuffer) {
    return new Uint8Array(maybeBuffer.from(base64, "base64"));
  }

  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);

  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }

  return bytes;
}

export async function deriveVaultKey(
  masterPassword: string,
  salt: Uint8Array,
  iterations: number
): Promise<CryptoKey> {
  const encoded = new TextEncoder().encode(masterPassword);

  const baseKey = await subtle().importKey(
    "raw",
    encoded,
    "PBKDF2",
    false,
    ["deriveKey"]
  );

  return subtle().deriveKey(
    {
      name: "PBKDF2",
      salt,
      iterations,
      hash: "SHA-256"
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

export async function encryptVaultWithKey(
  vault: Vault,
  key: CryptoKey
): Promise<{ iv: string; data: string }> {
  const iv = randomBytes(IV_BYTES);
  const plaintext = new TextEncoder().encode(JSON.stringify(vault));

  const ciphertext = await subtle().encrypt(
    {
      name: "AES-GCM",
      iv
    },
    key,
    plaintext
  );

  return {
    iv: bytesToBase64(iv),
    data: bytesToBase64(new Uint8Array(ciphertext))
  };
}

export async function decryptVaultWithKey(
  envelope: VaultEnvelope,
  key: CryptoKey
): Promise<Vault> {
  const iv = base64ToBytes(envelope.cipher.iv);
  const ciphertext = base64ToBytes(envelope.cipher.data);

  const plaintext = await subtle().decrypt(
    {
      name: "AES-GCM",
      iv
    },
    key,
    ciphertext
  );

  const decoded = new TextDecoder().decode(plaintext);
  const parsed = JSON.parse(decoded) as Vault;

  if (parsed.version !== 1 || !Array.isArray(parsed.entries)) {
    throw new Error("Invalid vault format");
  }

  return parsed;
}

export async function createVaultEnvelope(
  masterPassword: string,
  vault: Vault
): Promise<{ envelope: VaultEnvelope; key: CryptoKey }> {
  const now = Date.now();
  const salt = randomBytes(SALT_BYTES);
  const key = await deriveVaultKey(masterPassword, salt, KDF_ITERATIONS);
  const encrypted = await encryptVaultWithKey(vault, key);

  return {
    key,
    envelope: {
      version: 1,
      kdf: {
        name: "PBKDF2",
        hash: "SHA-256",
        iterations: KDF_ITERATIONS,
        salt: bytesToBase64(salt)
      },
      cipher: {
        alg: "AES-GCM",
        iv: encrypted.iv,
        data: encrypted.data
      },
      createdAt: now,
      updatedAt: now
    }
  };
}

export async function unlockVaultEnvelope(
  masterPassword: string,
  envelope: VaultEnvelope
): Promise<{ key: CryptoKey; vault: Vault }> {
  const salt = base64ToBytes(envelope.kdf.salt);

  const key = await deriveVaultKey(
    masterPassword,
    salt,
    envelope.kdf.iterations
  );

  const vault = await decryptVaultWithKey(envelope, key);

  return {
    key,
    vault
  };
}

export async function updateVaultEnvelope(
  existing: VaultEnvelope,
  key: CryptoKey,
  vault: Vault
): Promise<VaultEnvelope> {
  const encrypted = await encryptVaultWithKey(vault, key);

  return {
    ...existing,
    cipher: {
      alg: "AES-GCM",
      iv: encrypted.iv,
      data: encrypted.data
    },
    updatedAt: Date.now()
  };
}
```

---

## `src/storage.ts`

```ts
import type { VaultEnvelope } from "./types";

const VAULT_KEY = "pm_vault_v1";

export async function loadVaultEnvelope(): Promise<VaultEnvelope | null> {
  const result = await chrome.storage.local.get(VAULT_KEY);
  const envelope = result[VAULT_KEY] as VaultEnvelope | undefined;

  return envelope ?? null;
}

export async function saveVaultEnvelope(envelope: VaultEnvelope): Promise<void> {
  await chrome.storage.local.set({
    [VAULT_KEY]: envelope
  });
}

export async function vaultExists(): Promise<boolean> {
  return (await loadVaultEnvelope()) !== null;
}

export async function clearVaultForDevelopmentOnly(): Promise<void> {
  await chrome.storage.local.remove(VAULT_KEY);
}
```

---

## `src/background.ts`

```ts
import {
  createVaultEnvelope,
  decryptVaultWithKey,
  updateVaultEnvelope,
  unlockVaultEnvelope
} from "./crypto";
import { loadVaultEnvelope, saveVaultEnvelope, vaultExists } from "./storage";
import type {
  ApiResponse,
  PublicVaultEntry,
  Vault,
  VaultEntry
} from "./types";

let unlockedKey: CryptoKey | null = null;

const PRIVILEGED_MESSAGE_TYPES = new Set([
  "STATUS",
  "SETUP",
  "UNLOCK",
  "LOCK",
  "LIST_ACTIVE",
  "SAVE_ACTIVE_ENTRY",
  "DELETE_ENTRY",
  "FILL_ACTIVE_ENTRY"
]);

function publicEntry(entry: VaultEntry): PublicVaultEntry {
  return {
    id: entry.id,
    origin: entry.origin,
    username: entry.username,
    label: entry.label,
    updatedAt: entry.updatedAt
  };
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requireExtensionPage(sender: chrome.runtime.MessageSender): void {
  const senderUrl = sender.url ?? "";
  const expectedPrefix = `chrome-extension://${chrome.runtime.id}/`;

  if (sender.id !== chrome.runtime.id || !senderUrl.startsWith(expectedPrefix)) {
    throw new Error("Forbidden sender");
  }
}

function getOriginFromUrl(url: string | undefined): string | null {
  if (!url) return null;

  try {
    const parsed = new URL(url);

    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
      return null;
    }

    return parsed.origin;
  } catch {
    return null;
  }
}

function isAllowedOrigin(origin: string): boolean {
  try {
    const parsed = new URL(origin);

    if (parsed.protocol === "https:") {
      return true;
    }

    if (
      parsed.protocol === "http:" &&
      (parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1")
    ) {
      return true;
    }

    return false;
  } catch {
    return false;
  }
}

function normalizeOrigin(origin: string): string {
  const parsed = new URL(origin);
  return parsed.origin;
}

function validateString(
  value: unknown,
  field: string,
  min: number,
  max: number
): string {
  if (typeof value !== "string") {
    throw new Error(`${field} must be a string`);
  }

  const trimmed = value.trim();

  if (trimmed.length < min || trimmed.length > max) {
    throw new Error(`${field} length is invalid`);
  }

  return trimmed;
}

async function getActiveTab(): Promise<chrome.tabs.Tab> {
  const tabs = await chrome.tabs.query({
    active: true,
    currentWindow: true
  });

  const tab = tabs[0];

  if (!tab?.id) {
    throw new Error("No active tab");
  }

  return tab;
}

async function getActiveAllowedOrigin(): Promise<{
  tab: chrome.tabs.Tab;
  origin: string;
}> {
  const tab = await getActiveTab();
  const origin = getOriginFromUrl(tab.url);

  if (!origin || !isAllowedOrigin(origin)) {
    throw new Error("Unsupported page origin");
  }

  return {
    tab,
    origin
  };
}

async function decryptCurrentVault(): Promise<{
  envelope: NonNullable<Awaited<ReturnType<typeof loadVaultEnvelope>>>;
  vault: Vault;
}> {
  if (!unlockedKey) {
    throw new Error("Vault is locked");
  }

  const envelope = await loadVaultEnvelope();

  if (!envelope) {
    throw new Error("Vault is not set up");
  }

  const vault = await decryptVaultWithKey(envelope, unlockedKey);

  return {
    envelope,
    vault
  };
}

function generateId(): string {
  if (globalThis.crypto.randomUUID) {
    return globalThis.crypto.randomUUID();
  }

  const bytes = new Uint8Array(16);
  globalThis.crypto.getRandomValues(bytes);

  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function safeError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }

  return "Unexpected error";
}

async function handleMessage(
  message: unknown,
  sender: chrome.runtime.MessageSender
): Promise<ApiResponse> {
  if (!isPlainObject(message) || typeof message.type !== "string") {
    throw new Error("Invalid message");
  }

  const type = message.type;

  if (PRIVILEGED_MESSAGE_TYPES.has(type)) {
    requireExtensionPage(sender);
  }

  switch (type) {
    case "STATUS": {
      return {
        ok: true,
        data: {
          hasVault: await vaultExists(),
          unlocked: unlockedKey !== null
        }
      };
    }

    case "SETUP": {
      if (await vaultExists()) {
        throw new Error("Vault already exists");
      }

      const masterPassword = validateString(
        message.masterPassword,
        "masterPassword",
        12,
        1024
      );

      const emptyVault: Vault = {
        version: 1,
        entries: []
      };

      const { envelope, key } = await createVaultEnvelope(
        masterPassword,
        emptyVault
      );

      await saveVaultEnvelope(envelope);
      unlockedKey = key;

      return {
        ok: true
      };
    }

    case "UNLOCK": {
      const masterPassword = validateString(
        message.masterPassword,
        "masterPassword",
        1,
        1024
      );

      const envelope = await loadVaultEnvelope();

      if (!envelope) {
        throw new Error("Vault is not set up");
      }

      const { key } = await unlockVaultEnvelope(masterPassword, envelope);
      unlockedKey = key;

      return {
        ok: true
      };
    }

    case "LOCK": {
      unlockedKey = null;

      return {
        ok: true
      };
    }

    case "LIST_ACTIVE": {
      const { origin } = await getActiveAllowedOrigin();
      const { vault } = await decryptCurrentVault();

      return {
        ok: true,
        data: {
          origin,
          entries: vault.entries
            .filter((entry) => entry.origin === origin)
            .map(publicEntry)
        }
      };
    }

    case "SAVE_ACTIVE_ENTRY": {
      const { origin } = await getActiveAllowedOrigin();
      const normalizedOrigin = normalizeOrigin(origin);

      if (!isAllowedOrigin(normalizedOrigin)) {
        throw new Error("Refusing to save for insecure origin");
      }

      const username = validateString(message.username, "username", 1, 512);
      const password = validateString(message.password, "password", 1, 4096);
      const label =
        typeof message.label === "string"
          ? message.label.trim().slice(0, 128)
          : "";

      const id =
        typeof message.id === "string" && message.id.length <= 128
          ? message.id
          : null;

      const { envelope, vault } = await decryptCurrentVault();
      const now = Date.now();

      const existingIndex = id
        ? vault.entries.findIndex(
            (entry) => entry.id === id && entry.origin === normalizedOrigin
          )
        : -1;

      if (existingIndex >= 0) {
        const existing = vault.entries[existingIndex];

        if (!existing) {
          throw new Error("Entry not found");
        }

        vault.entries[existingIndex] = {
          ...existing,
          username,
          password,
          label,
          updatedAt: now
        };
      } else {
        vault.entries.push({
          id: generateId(),
          origin: normalizedOrigin,
          username,
          password,
          label,
          createdAt: now,
          updatedAt: now
        });
      }

      const updated = await updateVaultEnvelope(envelope, unlockedKey!, vault);
      await saveVaultEnvelope(updated);

      return {
        ok: true
      };
    }

    case "DELETE_ENTRY": {
      const id = validateString(message.id, "id", 1, 128);
      const { origin } = await getActiveAllowedOrigin();
      const { envelope, vault } = await decryptCurrentVault();

      vault.entries = vault.entries.filter(
        (entry) => !(entry.id === id && entry.origin === origin)
      );

      const updated = await updateVaultEnvelope(envelope, unlockedKey!, vault);
      await saveVaultEnvelope(updated);

      return {
        ok: true
      };
    }

    case "FILL_ACTIVE_ENTRY": {
      const id = validateString(message.id, "id", 1, 128);
      const { tab, origin } = await getActiveAllowedOrigin();
      const { vault } = await decryptCurrentVault();

      const entry = vault.entries.find(
        (candidate) => candidate.id === id && candidate.origin === origin
      );

      if (!entry) {
        throw new Error("Entry not found for active origin");
      }

      await chrome.tabs.sendMessage(tab.id!, {
        type: "FILL_LOGIN",
        username: entry.username,
        password: entry.password
      });

      return {
        ok: true
      };
    }

    case "FORM_DETECTED": {
      if (!sender.tab?.id) {
        throw new Error("Invalid sender tab");
      }

      const claimedOrigin =
        typeof message.origin === "string" ? message.origin : "";
      const senderOrigin = getOriginFromUrl(sender.tab.url);

      if (!senderOrigin || claimedOrigin !== senderOrigin) {
        throw new Error("Origin mismatch");
      }

      await chrome.action.setBadgeText({
        tabId: sender.tab.id,
        text: "PM"
      });

      await chrome.action.setBadgeBackgroundColor({
        tabId: sender.tab.id,
        color: "#1a73e8"
      });

      return {
        ok: true
      };
    }

    default:
      throw new Error("Unknown message type");
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  handleMessage(message, sender)
    .then(sendResponse)
    .catch((error: unknown) => {
      sendResponse({
        ok: false,
        error: safeError(error)
      } satisfies ApiResponse);
    });

  return true;
});
```

---

## `src/content.ts`

```ts
function isVisibleInput(input: HTMLInputElement): boolean {
  if (input.disabled || input.readOnly) return false;

  const style = window.getComputedStyle(input);

  if (
    style.display === "none" ||
    style.visibility === "hidden" ||
    style.opacity === "0"
  ) {
    return false;
  }

  const rect = input.getBoundingClientRect();

  return rect.width > 0 && rect.height > 0;
}

function hasPasswordForm(): boolean {
  return [...document.querySelectorAll("input[type='password']")].some(
    (input) => input instanceof HTMLInput
