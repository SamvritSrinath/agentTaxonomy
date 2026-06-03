import { apiClient } from '../lib/api-client';
import { KeyManager } from '../lib/key-manager';
import { encryptVault, decryptVault } from '../lib/crypto';

export async function syncVault(keyManager: KeyManager): Promise<void> {
  const localVaultJson = await chrome.storage.local.get('vault');
  const { iv, ciphertext } = await encryptVault(localVaultJson, keyManager.key);
  const serverResp = await apiClient.put('/vault/sync', { iv: Array.from(iv), ciphertext: Array.from(new Uint8Array(ciphertext)) });
  // Handle merge conflicts using server version vector clocks
}
