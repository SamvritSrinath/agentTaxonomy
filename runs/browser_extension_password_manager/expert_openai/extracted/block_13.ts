import type { Session } from "./types";

const API_BASE = "https://api.example.com";

export async function getSession(): Promise<Session | null> {
  const result = await chrome.storage.session.get("session");
  return (result.session as Session | undefined) ?? null;
}

export async function setSession(session: Session): Promise<void> {
  await chrome.storage.session.set({ session });
}

export async function loginWithOidcPkce(): Promise<Session> {
  const redirectUrl = chrome.identity.getRedirectURL("oidc");
  const authUrl = new URL("https://app.example.com/oauth/authorize");

  authUrl.searchParams.set("client_id", "chrome-extension");
  authUrl.searchParams.set("response_type", "code");
  authUrl.searchParams.set("redirect_uri", redirectUrl);
  authUrl.searchParams.set("scope", "openid profile email");
  authUrl.searchParams.set("state", crypto.randomUUID());

  const responseUrl = await chrome.identity.launchWebAuthFlow({
    url: authUrl.toString(),
    interactive: true
  });

  const code = new URL(responseUrl).searchParams.get("code");
  if (!code) throw new Error("Missing authorization code");

  const res = await fetch(`${API_BASE}/auth/extension-token`, {
    method: "POST",
    headers: {
      "content-type": "application/json"
    },
    credentials: "omit",
    body: JSON.stringify({
      code,
      redirectUri: redirectUrl
    })
  });

  if (!res.ok) throw new Error("Authentication failed");

  const session = (await res.json()) as Session;
  await setSession(session);
  return session;
}
