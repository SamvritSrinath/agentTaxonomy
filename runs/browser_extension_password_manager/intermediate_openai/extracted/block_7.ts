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
