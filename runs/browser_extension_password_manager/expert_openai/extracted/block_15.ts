import { loginWithOidcPkce, getSession } from "./auth";
import { pullVault, pushVault } from "./vaultClient";
import type { BackgroundRequest } from "./types";

chrome.runtime.onMessage.addListener((msg: BackgroundRequest, sender, sendResponse) => {
  void handleMessage(msg, sender)
    .then(sendResponse)
    .catch(err => sendResponse({ error: err instanceof Error ? err.message : "Unknown error" }));

  return true;
});

async function handleMessage(msg: BackgroundRequest, sender: chrome.runtime.MessageSender) {
  switch (msg.type) {
    case "AUTH_LOGIN":
      return loginWithOidcPkce();

    case "SYNC_PULL": {
      const session = await requireSession();
      return pullVault(session, msg.masterSecret);
    }

    case "SYNC_PUSH": {
      const session = await requireSession();
      return pushVault(session, msg.masterSecret, msg.state);
    }

    case "FILL_CREDENTIAL": {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab.id || !tab.url?.startsWith("https://")) {
        throw new Error("Can only fill into active HTTPS tabs");
      }

      const tabOrigin = new URL(tab.url).origin;
      if (new URL(msg.record.origin).origin !== tabOrigin) {
        throw new Error("Credential origin mismatch");
      }

      await chrome.tabs.sendMessage(tab.id, {
        type: "PM_FILL",
        username: msg.record.username,
        password: msg.record.password,
        origin: msg.record.origin
      });

      return { ok: true };
    }
  }
}

async function requireSession() {
  const session = await getSession();
  if (!session || session.expiresAt < Date.now() + 30_000) {
    throw new Error("Not authenticated");
  }
  return session;
}
