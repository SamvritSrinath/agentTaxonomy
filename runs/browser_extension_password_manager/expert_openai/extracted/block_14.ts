import { decryptJson, encryptJson, VaultRecord } from "@pm/crypto";
import type { Session, SyncEnvelope, VaultState } from "./types";

const API_BASE = "https://api.example.com";

export async function pullVault(
  session: Session,
  masterSecret: string
): Promise<VaultState> {
  const res = await fetch(`${API_BASE}/vault`, {
    headers: {
      authorization: `Bearer ${session.accessToken}`
    }
  });

  if (res.status === 404) {
    return { records: [], version: 0 };
  }

  if (!res.ok) throw new Error("Failed to pull vault");

  const envelope = (await res.json()) as SyncEnvelope;
  const records = await decryptJson<VaultRecord[]>(
    envelope.encryptedVault,
    masterSecret
  );

  return {
    records,
    version: envelope.vaultVersion
  };
}

export async function pushVault(
  session: Session,
  masterSecret: string,
  state: VaultState
): Promise<VaultState> {
  const encryptedVault = await encryptJson(state.records, masterSecret);

  const res = await fetch(`${API_BASE}/vault`, {
    method: "PUT",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${session.accessToken}`,
      "if-match": String(state.version)
    },
    body: JSON.stringify({ encryptedVault })
  });

  if (res.status === 409) {
    throw new Error("Vault conflict. Pull latest and merge.");
  }

  if (!res.ok) throw new Error("Failed to push vault");

  return (await res.json()) as VaultState;
}
