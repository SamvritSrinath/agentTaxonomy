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
