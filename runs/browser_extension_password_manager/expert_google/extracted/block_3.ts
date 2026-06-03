export interface DerivedKeys {
  authHash: string;
  dataKey: CryptoKey;
}

/**
 * Derives the Auth Hash (sent to server) and Data Key (kept in memory for encryption)
 * using PBKDF2 with SHA-256. Zero-knowledge design.
 */
export async function deriveKeys(password: string, email: string, salt: string): Promise<DerivedKeys> {
  const encoder = new TextEncoder();
  const passwordBytes = encoder.encode(password);
  const saltBytes = encoder.encode(email + salt);

  // Import raw password bytes as a key
  const baseKey = await crypto.subtle.importKey(
    'raw',
    passwordBytes,
    { name: 'PBKDF2' },
    false,
    ['deriveKey', 'deriveBits']
  );

  // Derive Master Key (100,000 iterations)
  const masterKeyBits = await crypto.subtle.deriveBits(
    {
      name: 'PBKDF2',
      salt: saltBytes,
      iterations: 100000,
      hash: 'SHA-256'
    },
    baseKey,
    256
  );

  // Derive Data Key (for local encryption/decryption)
  const dataKey = await crypto.subtle.importKey(
    'raw',
    masterKeyBits,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt']
  );

  // Derive Auth Hash (to authenticate with the server)
  const authKeyBase = await crypto.subtle.importKey(
    'raw',
    masterKeyBits,
    { name: 'PBKDF2' },
    false,
    ['deriveBits']
  );

  const authHashBits = await crypto.subtle.deriveBits(
    {
      name: 'PBKDF2',
      salt: encoder.encode('auth-salt-constant'),
      iterations: 1,
      hash: 'SHA-256'
    },
    authKeyBase,
    256
  );

  const authHash = bufToHex(authHashBits);

  return { authHash, dataKey };
}

/**
 * Encrypts plaintext using AES-GCM-256
 */
export async function encryptData(plaintext: string, key: CryptoKey): Promise<{ ciphertext: string; iv: string }> {
  const encoder = new TextEncoder();
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encrypted = await crypto.subtle.encrypt(
    {
      name: 'AES-GCM',
      iv: iv
    },
    key,
    encoder.encode(plaintext)
  );

  return {
    ciphertext: bufToHex(encrypted),
    iv: bufToHex(iv.buffer)
  };
}

/**
 * Decrypts ciphertext using AES-GCM-256
 */
export async function decryptData(ciphertextHex: string, ivHex: string, key: CryptoKey): Promise<string> {
  const decoder = new TextDecoder();
  const ciphertext = hexToBuf(ciphertextHex);
  const iv = hexToBuf(ivHex);

  const decrypted = await crypto.subtle.decrypt(
    {
      name: 'AES-GCM',
      iv: new Uint8Array(iv)
    },
    key,
    ciphertext
  );

  return decoder.decode(decrypted);
}

// Helper utilities
function bufToHex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

function hexToBuf(hex: string): ArrayBuffer {
  const view = new Uint8Array(hex.length / 2);
  for (let i = 0; i < view.length; i++) {
    view[i] = parseInt(hex.substring(i * 2, i * 2 + 2), 16);
  }
  return view.buffer;
}
