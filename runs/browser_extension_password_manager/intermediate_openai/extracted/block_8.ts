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
