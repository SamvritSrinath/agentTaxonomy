import { deriveKey, encryptVault, decryptVault } from '../src/lib/crypto';

test('encrypt/decrypt roundtrip', async () => {
  const key = await deriveKey('test123', crypto.getRandomValues(new Uint8Array(16)));
  const data = new TextEncoder().encode('secret data').buffer;
  const { iv, ciphertext } = await encryptVault(data, key);
  const decrypted = await decryptVault(ciphertext, iv, key);
  expect(new Uint8Array(decrypted)).toEqual(new Uint8Array(data));
});
