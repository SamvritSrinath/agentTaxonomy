// aes.js - All cryptographic operations
const AES_ALGO = 'AES-GCM';
const KEY_DERIVE = { name: 'PBKDF2', hash: 'SHA-256', iterations: 100000 };
const KEY_USAGE = ['encrypt', 'decrypt'];

// Convert ArrayBuffer <-> base64
function arrayBufferToBase64(buffer) {
  return btoa(String.fromCharCode(...new Uint8Array(buffer)));
}
function base64ToArrayBuffer(b64) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

// Derive a CryptoKey from a master password + salt
async function deriveKey(password, salt) {
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(password),
    'PBKDF2',
    false,
    ['deriveKey']
  );
  return crypto.subtle.deriveKey(
    { ...KEY_DERIVE, salt: salt instanceof ArrayBuffer ? salt : base64ToArrayBuffer(salt) },
    keyMaterial,
    { name: AES_ALGO, length: 256 },
    false,
    KEY_USAGE
  );
}

// Encrypts plaintext (string) with key, returns { iv, ciphertext } (both base64)
async function encrypt(plaintext, key) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encoded = new TextEncoder().encode(plaintext);
  const ciphertext = await crypto.subtle.encrypt(
    { name: AES_ALGO, iv },
    key,
    encoded
  );
  return {
    iv: arrayBufferToBase64(iv.buffer),
    ciphertext: arrayBufferToBase64(ciphertext)
  };
}

// Decrypts ciphertext (base64) with iv (base64) and key, returns plaintext string
async function decrypt(ivB64, ciphertextB64, key) {
  const iv = new Uint8Array(base64ToArrayBuffer(ivB64));
  const ct = new Uint8Array(base64ToArrayBuffer(ciphertextB64));
  const plainBuffer = await crypto.subtle.decrypt({ name: AES_ALGO, iv }, key, ct);
  return new TextDecoder().decode(plainBuffer);
}

export { deriveKey, encrypt, decrypt, arrayBufferToBase64, base64ToArrayBuffer };
