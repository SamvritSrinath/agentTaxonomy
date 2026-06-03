import type { EncryptedPayload, VaultRecord } from "@pm/crypto";

export type Session = {
  accessToken: string;
  expiresAt: number;
};

export type VaultState = {
  records: VaultRecord[];
  version: number;
};

export type SyncEnvelope = {
  vaultVersion: number;
  encryptedVault: EncryptedPayload;
};

export type BackgroundRequest =
  | { type: "AUTH_LOGIN" }
  | { type: "SYNC_PULL"; masterSecret: string }
  | { type: "SYNC_PUSH"; masterSecret: string; state: VaultState }
  | { type: "FILL_CREDENTIAL"; record: VaultRecord };
