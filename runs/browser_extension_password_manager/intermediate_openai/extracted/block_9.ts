import {
  createVaultEnvelope,
  decryptVaultWithKey,
  updateVaultEnvelope,
  unlockVaultEnvelope
} from "./crypto";
import { loadVaultEnvelope, saveVaultEnvelope, vaultExists } from "./storage";
import type {
  ApiResponse,
  PublicVaultEntry,
  Vault,
  VaultEntry
} from "./types";

let unlockedKey: CryptoKey | null = null;

const PRIVILEGED_MESSAGE_TYPES = new Set([
  "STATUS",
  "SETUP",
  "UNLOCK",
  "LOCK",
  "LIST_ACTIVE",
  "SAVE_ACTIVE_ENTRY",
  "DELETE_ENTRY",
  "FILL_ACTIVE_ENTRY"
]);

function publicEntry(entry: VaultEntry): PublicVaultEntry {
  return {
    id: entry.id,
    origin: entry.origin,
    username: entry.username,
    label: entry.label,
    updatedAt: entry.updatedAt
  };
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function requireExtensionPage(sender: chrome.runtime.MessageSender): void {
  const senderUrl = sender.url ?? "";
  const expectedPrefix = `chrome-extension://${chrome.runtime.id}/`;

  if (sender.id !== chrome.runtime.id || !senderUrl.startsWith(expectedPrefix)) {
    throw new Error("Forbidden sender");
  }
}

function getOriginFromUrl(url: string | undefined): string | null {
  if (!url) return null;

  try {
    const parsed = new URL(url);

    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
      return null;
    }

    return parsed.origin;
  } catch {
    return null;
  }
}

function isAllowedOrigin(origin: string): boolean {
  try {
    const parsed = new URL(origin);

    if (parsed.protocol === "https:") {
      return true;
    }

    if (
      parsed.protocol === "http:" &&
      (parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1")
    ) {
      return true;
    }

    return false;
  } catch {
    return false;
  }
}

function normalizeOrigin(origin: string): string {
  const parsed = new URL(origin);
  return parsed.origin;
}

function validateString(
  value: unknown,
  field: string,
  min: number,
  max: number
): string {
  if (typeof value !== "string") {
    throw new Error(`${field} must be a string`);
  }

  const trimmed = value.trim();

  if (trimmed.length < min || trimmed.length > max) {
    throw new Error(`${field} length is invalid`);
  }

  return trimmed;
}

async function getActiveTab(): Promise<chrome.tabs.Tab> {
  const tabs = await chrome.tabs.query({
    active: true,
    currentWindow: true
  });

  const tab = tabs[0];

  if (!tab?.id) {
    throw new Error("No active tab");
  }

  return tab;
}

async function getActiveAllowedOrigin(): Promise<{
  tab: chrome.tabs.Tab;
  origin: string;
}> {
  const tab = await getActiveTab();
  const origin = getOriginFromUrl(tab.url);

  if (!origin || !isAllowedOrigin(origin)) {
    throw new Error("Unsupported page origin");
  }

  return {
    tab,
    origin
  };
}

async function decryptCurrentVault(): Promise<{
  envelope: NonNullable<Awaited<ReturnType<typeof loadVaultEnvelope>>>;
  vault: Vault;
}> {
  if (!unlockedKey) {
    throw new Error("Vault is locked");
  }

  const envelope = await loadVaultEnvelope();

  if (!envelope) {
    throw new Error("Vault is not set up");
  }

  const vault = await decryptVaultWithKey(envelope, unlockedKey);

  return {
    envelope,
    vault
  };
}

function generateId(): string {
  if (globalThis.crypto.randomUUID) {
    return globalThis.crypto.randomUUID();
  }

  const bytes = new Uint8Array(16);
  globalThis.crypto.getRandomValues(bytes);

  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function safeError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }

  return "Unexpected error";
}

async function handleMessage(
  message: unknown,
  sender: chrome.runtime.MessageSender
): Promise<ApiResponse> {
  if (!isPlainObject(message) || typeof message.type !== "string") {
    throw new Error("Invalid message");
  }

  const type = message.type;

  if (PRIVILEGED_MESSAGE_TYPES.has(type)) {
    requireExtensionPage(sender);
  }

  switch (type) {
    case "STATUS": {
      return {
        ok: true,
        data: {
          hasVault: await vaultExists(),
          unlocked: unlockedKey !== null
        }
      };
    }

    case "SETUP": {
      if (await vaultExists()) {
        throw new Error("Vault already exists");
      }

      const masterPassword = validateString(
        message.masterPassword,
        "masterPassword",
        12,
        1024
      );

      const emptyVault: Vault = {
        version: 1,
        entries: []
      };

      const { envelope, key } = await createVaultEnvelope(
        masterPassword,
        emptyVault
      );

      await saveVaultEnvelope(envelope);
      unlockedKey = key;

      return {
        ok: true
      };
    }

    case "UNLOCK": {
      const masterPassword = validateString(
        message.masterPassword,
        "masterPassword",
        1,
        1024
      );

      const envelope = await loadVaultEnvelope();

      if (!envelope) {
        throw new Error("Vault is not set up");
      }

      const { key } = await unlockVaultEnvelope(masterPassword, envelope);
      unlockedKey = key;

      return {
        ok: true
      };
    }

    case "LOCK": {
      unlockedKey = null;

      return {
        ok: true
      };
    }

    case "LIST_ACTIVE": {
      const { origin } = await getActiveAllowedOrigin();
      const { vault } = await decryptCurrentVault();

      return {
        ok: true,
        data: {
          origin,
          entries: vault.entries
            .filter((entry) => entry.origin === origin)
            .map(publicEntry)
        }
      };
    }

    case "SAVE_ACTIVE_ENTRY": {
      const { origin } = await getActiveAllowedOrigin();
      const normalizedOrigin = normalizeOrigin(origin);

      if (!isAllowedOrigin(normalizedOrigin)) {
        throw new Error("Refusing to save for insecure origin");
      }

      const username = validateString(message.username, "username", 1, 512);
      const password = validateString(message.password, "password", 1, 4096);
      const label =
        typeof message.label === "string"
          ? message.label.trim().slice(0, 128)
          : "";

      const id =
        typeof message.id === "string" && message.id.length <= 128
          ? message.id
          : null;

      const { envelope, vault } = await decryptCurrentVault();
      const now = Date.now();

      const existingIndex = id
        ? vault.entries.findIndex(
            (entry) => entry.id === id && entry.origin === normalizedOrigin
          )
        : -1;

      if (existingIndex >= 0) {
        const existing = vault.entries[existingIndex];

        if (!existing) {
          throw new Error("Entry not found");
        }

        vault.entries[existingIndex] = {
          ...existing,
          username,
          password,
          label,
          updatedAt: now
        };
      } else {
        vault.entries.push({
          id: generateId(),
          origin: normalizedOrigin,
          username,
          password,
          label,
          createdAt: now,
          updatedAt: now
        });
      }

      const updated = await updateVaultEnvelope(envelope, unlockedKey!, vault);
      await saveVaultEnvelope(updated);

      return {
        ok: true
      };
    }

    case "DELETE_ENTRY": {
      const id = validateString(message.id, "id", 1, 128);
      const { origin } = await getActiveAllowedOrigin();
      const { envelope, vault } = await decryptCurrentVault();

      vault.entries = vault.entries.filter(
        (entry) => !(entry.id === id && entry.origin === origin)
      );

      const updated = await updateVaultEnvelope(envelope, unlockedKey!, vault);
      await saveVaultEnvelope(updated);

      return {
        ok: true
      };
    }

    case "FILL_ACTIVE_ENTRY": {
      const id = validateString(message.id, "id", 1, 128);
      const { tab, origin } = await getActiveAllowedOrigin();
      const { vault } = await decryptCurrentVault();

      const entry = vault.entries.find(
        (candidate) => candidate.id === id && candidate.origin === origin
      );

      if (!entry) {
        throw new Error("Entry not found for active origin");
      }

      await chrome.tabs.sendMessage(tab.id!, {
        type: "FILL_LOGIN",
        username: entry.username,
        password: entry.password
      });

      return {
        ok: true
      };
    }

    case "FORM_DETECTED": {
      if (!sender.tab?.id) {
        throw new Error("Invalid sender tab");
      }

      const claimedOrigin =
        typeof message.origin === "string" ? message.origin : "";
      const senderOrigin = getOriginFromUrl(sender.tab.url);

      if (!senderOrigin || claimedOrigin !== senderOrigin) {
        throw new Error("Origin mismatch");
      }

      await chrome.action.setBadgeText({
        tabId: sender.tab.id,
        text: "PM"
      });

      await chrome.action.setBadgeBackgroundColor({
        tabId: sender.tab.id,
        color: "#1a73e8"
      });

      return {
        ok: true
      };
    }

    default:
      throw new Error("Unknown message type");
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  handleMessage(message, sender)
    .then(sendResponse)
    .catch((error: unknown) => {
      sendResponse({
        ok: false,
        error: safeError(error)
      } satisfies ApiResponse);
    });

  return true;
});
