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
