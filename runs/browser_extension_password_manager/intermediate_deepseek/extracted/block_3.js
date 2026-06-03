(function(global) {
  'use strict';
  const AES_ALGO = 'AES-GCM';
  const KEY_DERIVE = { name: 'PBKDF2', hash: 'SHA-256', iterations: 100000 };
  const KEY_USAGE = ['encrypt', 'decrypt'];

  global.arrayBufferToBase64 = function (buffer) {
    return btoa(String.fromCharCode(...new Uint8Array(buffer)));
  };
  global.base64ToArrayBuffer = function (b64) {
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return bytes.buffer;
  };
  global.deriveKey = async function (password, salt) {
    const keyMaterial = await crypto.subtle.importKey(
      'raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveKey']
    );
    return crypto.subtle.deriveKey(
      { ...KEY_DERIVE, salt },
      keyMaterial,
      { name: AES_ALGO, length: 256 },
      false,
      KEY_USAGE
    );
  };
  global.encrypt = async function (plaintext, key) {
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const encoded = new TextEncoder().encode(plaintext);
    const ciphertext = await crypto.subtle.encrypt({ name: AES_ALGO, iv }, key, encoded);
    return {
      iv: arrayBufferToBase64(iv.buffer),
      ciphertext: arrayBufferToBase64(ciphertext)
    };
  };
  global.decrypt = async function (ivB64, ciphertextB64, key) {
    const iv = new Uint8Array(base64ToArrayBuffer(ivB64));
    const ct = new Uint8Array(base64ToArrayBuffer(ciphertextB64));
    const plainBuffer = await crypto.subtle.decrypt({ name: AES_ALGO, iv }, key, ct);
    return new TextDecoder().decode(plainBuffer);
  };
})(self);
