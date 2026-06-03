export interface VaultEntry {
  id: string;
  origin: string;
  username: string;
  password: string;
  label: string;
  createdAt: number;
  updatedAt: number;
}

export interface PublicVaultEntry {
  id: string;
  origin: string;
  username: string;
  label: string;
  updatedAt: number;
}

export interface Vault {
  version: 1;
  entries: VaultEntry[];
}

export interface VaultEnvelope {
  version: 1;
  kdf: {
    name: "PBKDF2";
    hash: "SHA-256";
    iterations: number;
    salt: string;
  };
  cipher: {
    alg: "AES-GCM";
    iv: string;
    data: string;
  };
  createdAt: number;
  updatedAt: number;
}

export interface ApiResponse<T = unknown> {
  ok: boolean;
  data?: T;
  error?: string;
}
