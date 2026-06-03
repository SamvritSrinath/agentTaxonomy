import { decryptData, deriveKeys } from './utils/crypto';

// In-memory state (cleared when extension locks or service worker suspends)
let sessionKey: CryptoKey | null = null;
let cachedVault: any[] | null = null;
const API_URL = 'https://api.securevault.internal/api';

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  // Enforce internal message origin validation
  if (sender.id !== chrome.runtime.id) {
    sendResponse({ error: 'Unauthorized sender' });
    return;
  }

  handleMessage(message, sendResponse);
  return true; // Keep message channel open for async responses
});

async function handleMessage(message: any, sendResponse: (response: any) => void) {
  try {
    switch (message.type) {
      case 'LOGIN': {
        const { email, password } = message.payload;
        // 1. Fetch salt from server
        const saltRes = await fetch(`${API_URL}/auth/salt?email=${encodeURIComponent(email)}`);
        const { salt } = await saltRes.json();

        // 2. Derive keys
        const { authHash, dataKey } = await deriveKeys(password, email, salt);

        // 3. Authenticate with server
        const loginRes = await fetch(`${API_URL}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, authHash })
        });

        if (!loginRes.ok) throw new Error('Invalid credentials');
        const { token, encryptedVault, iv } = await loginRes.json();

        // Store session key in memory
        sessionKey = dataKey;
        await chrome.storage.local.set({ token });

        // Decrypt vault if it exists
        if (encryptedVault && iv) {
          const decrypted = await decryptData(encryptedVault, iv, sessionKey);
          cachedVault = JSON.parse(decrypted);
        } else {
          cachedVault = [];
        }

        sendResponse({ success: true, vault: cachedVault });
        break;
      }

      case 'GET_VAULT': {
        if (!sessionKey) {
          sendResponse({ error: 'LOCKED' });
        } else {
          sendResponse({ success: true, vault: cachedVault });
        }
        break;
      }

      case 'LOCK': {
        sessionKey = null;
        cachedVault = null;
        await chrome.storage.local.remove('token');
        sendResponse({ success: true });
        break;
      }

      default:
        sendResponse({ error: 'Unknown action' });
    }
  } catch (err: any) {
    sendResponse({ error: err.message });
  }
}
