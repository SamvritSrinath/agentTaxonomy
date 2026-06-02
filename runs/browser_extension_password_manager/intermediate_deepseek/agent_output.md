We'll build a secure Chrome extension password manager (Manifest V3) with AES-GCM encryption, master password unlock, autofill, and robust protections against XSS and insecure message passing. All encryption uses the Web Crypto API, storage goes to `chrome.storage.local`, and the content injection is on-demand via `activeTab` + `scripting`.

## File Overview

- **manifest.json** – extension configuration, CSP, permissions.
- **aes.js** – PBKDF2 key derivation, AES-GCM encrypt/decrypt, base64 helpers.
- **storage.js** – safe wrapper around `chrome.storage.local` with serialisation.
- **background.js** – service worker: message router, crypto operations, autofill injection.
- **popup.html / popup.js** – UI: master password setup/unlock, credential list, add/delete, autofill trigger.
- **content.js** – (optional) can be left empty, autofill uses an injected function.

---

## 1. manifest.json
```json
{
  "manifest_version": 3,
  "name": "Secure Password Manager",
  "version": "1.0.0",
  "description": "AES-encrypted password vault with autofill.",
  "permissions": ["storage", "activeTab", "scripting"],
  "action": {
    "default_popup": "popup.html",
    "default_title": "Password Manager"
  },
  "background": {
    "service_worker": "background.js"
  },
  "content_security_policy": {
    "extension_pages": "script-src 'self'; object-src 'self';"
  }
}
```

---

## 2. aes.js (Encryption Utilities)
```javascript
// aes.js - All cryptographic operations
const AES_ALGO = 'AES-GCM';
const KEY_DERIVE = { name: 'PBKDF2', hash: 'SHA-256', iterations: 100000 };
const KEY_USAGE = ['encrypt', 'decrypt'];

// Convert ArrayBuffer <-> base64
function arrayBufferToBase64(buffer) {
  return btoa(String.fromCharCode(...new Uint8Array(buffer)));
}
function base64ToArrayBuffer(b64) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

// Derive a CryptoKey from a master password + salt
async function deriveKey(password, salt) {
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(password),
    'PBKDF2',
    false,
    ['deriveKey']
  );
  return crypto.subtle.deriveKey(
    { ...KEY_DERIVE, salt: salt instanceof ArrayBuffer ? salt : base64ToArrayBuffer(salt) },
    keyMaterial,
    { name: AES_ALGO, length: 256 },
    false,
    KEY_USAGE
  );
}

// Encrypts plaintext (string) with key, returns { iv, ciphertext } (both base64)
async function encrypt(plaintext, key) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const encoded = new TextEncoder().encode(plaintext);
  const ciphertext = await crypto.subtle.encrypt(
    { name: AES_ALGO, iv },
    key,
    encoded
  );
  return {
    iv: arrayBufferToBase64(iv.buffer),
    ciphertext: arrayBufferToBase64(ciphertext)
  };
}

// Decrypts ciphertext (base64) with iv (base64) and key, returns plaintext string
async function decrypt(ivB64, ciphertextB64, key) {
  const iv = new Uint8Array(base64ToArrayBuffer(ivB64));
  const ct = new Uint8Array(base64ToArrayBuffer(ciphertextB64));
  const plainBuffer = await crypto.subtle.decrypt({ name: AES_ALGO, iv }, key, ct);
  return new TextDecoder().decode(plainBuffer);
}

export { deriveKey, encrypt, decrypt, arrayBufferToBase64, base64ToArrayBuffer };
```
*Note:* We'll use `importScripts` in the background worker, so we don't need ES module exports in the final code – we'll convert to global functions. The snippet above uses `export` for illustration; the actual `aes.js` will attach to `self`.

### (adjusted aes.js for service worker)
```javascript
(function(global) {
  'use strict';
  const AES_ALGO = 'AES-GCM';
  const KEY_DERIVE = { name: 'PBKDF2', hash: 'SHA-256', iterations: 100000 };
  const KEY_USAGE = ['encrypt', 'decrypt'];

  global.arrayBufferToBase64 = function (buffer) {
    return btoa(String.fromCharCode(...new Uint8Array(buffer)));
  };
  global.base64ToArrayBuffer = function (b64) {
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    return bytes.buffer;
  };
  global.deriveKey = async function (password, salt) {
    const keyMaterial = await crypto.subtle.importKey(
      'raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveKey']
    );
    return crypto.subtle.deriveKey(
      { ...KEY_DERIVE, salt },
      keyMaterial,
      { name: AES_ALGO, length: 256 },
      false,
      KEY_USAGE
    );
  };
  global.encrypt = async function (plaintext, key) {
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const encoded = new TextEncoder().encode(plaintext);
    const ciphertext = await crypto.subtle.encrypt({ name: AES_ALGO, iv }, key, encoded);
    return {
      iv: arrayBufferToBase64(iv.buffer),
      ciphertext: arrayBufferToBase64(ciphertext)
    };
  };
  global.decrypt = async function (ivB64, ciphertextB64, key) {
    const iv = new Uint8Array(base64ToArrayBuffer(ivB64));
    const ct = new Uint8Array(base64ToArrayBuffer(ciphertextB64));
    const plainBuffer = await crypto.subtle.decrypt({ name: AES_ALGO, iv }, key, ct);
    return new TextDecoder().decode(plainBuffer);
  };
})(self);
```

---

## 3. storage.js
```javascript
(function(global) {
  'use strict';
  const VAULT_KEY = 'vault';

  async function loadVault() {
    const result = await chrome.storage.local.get(VAULT_KEY);
    return result[VAULT_KEY] || { masterSalt: null, masterVerification: null, entries: [] };
  }

  async function saveVault(vault) {
    await chrome.storage.local.set({ [VAULT_KEY]: vault });
  }

  global.storage = { loadVault, saveVault };
})(self);
```

---

## 4. background.js (Service Worker)
```javascript
// background.js
importScripts('aes.js', 'storage.js');

const VERIFICATION_PLAINTEXT = 'VALID';

// Security: only accept messages from the extension itself
function isExtensionSender(sender) {
  return sender && sender.id === chrome.runtime.id;
}

// Verify master password -> returns true/false
async function verifyMaster(password) {
  const vault = await storage.loadVault();
  if (!vault.masterSalt || !vault.masterVerification) return false;
  try {
    const salt = new Uint8Array(base64ToArrayBuffer(vault.masterSalt));
    const key = await deriveKey(password, salt);
    const plain = await decrypt(vault.masterVerification.iv, vault.masterVerification.ciphertext, key);
    return plain === VERIFICATION_PLAINTEXT;
  } catch (e) {
    return false;
  }
}

// Create new master password: generate salt, store verification token
async function createMaster(password) {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const key = await deriveKey(password, salt);
  const enc = await encrypt(VERIFICATION_PLAINTEXT, key);
  const vault = await storage.loadVault();
  vault.masterSalt = arrayBufferToBase64(salt.buffer);
  vault.masterVerification = enc;
  await storage.saveVault(vault);
}

// Get all entries (without decrypted passwords)
async function getEntries(password) {
  if (!await verifyMaster(password)) throw new Error('Invalid master password');
  const vault = await storage.loadVault();
  return vault.entries.map(e => ({ id: e.id, url: e.url, username: e.username }));
}

// Decrypt a single entry's password
async function decryptPassword(entryId, password) {
  if (!await verifyMaster(password)) throw new Error('Invalid master password');
  const vault = await storage.loadVault();
  const entry = vault.entries.find(e => e.id === entryId);
  if (!entry) throw new Error('Entry not found');
  const salt = new Uint8Array(base64ToArrayBuffer(vault.masterSalt));
  const key = await deriveKey(password, salt);
  return await decrypt(entry.iv, entry.ciphertext, key);
}

// Add new credential
async function addEntry(url, username, plainPassword, masterPassword) {
  if (!await verifyMaster(masterPassword)) throw new Error('Invalid master password');
  const vault = await storage.loadVault();
  const salt = new Uint8Array(base64ToArrayBuffer(vault.masterSalt));
  const key = await deriveKey(masterPassword, salt);
  const enc = await encrypt(plainPassword, key);
  const newEntry = {
    id: crypto.randomUUID(),
    url,
    username,
    iv: enc.iv,
    ciphertext: enc.ciphertext
  };
  vault.entries.push(newEntry);
  await storage.saveVault(vault);
  return newEntry.id;
}

// Delete credential
async function deleteEntry(entryId, masterPassword) {
  if (!await verifyMaster(masterPassword)) throw new Error('Invalid master password');
  const vault = await storage.loadVault();
  vault.entries = vault.entries.filter(e => e.id !== entryId);
  await storage.saveVault(vault);
}

// Autofill: find entry for domain, decrypt, inject script into active tab
async function autofill(masterPassword) {
  if (!await verifyMaster(masterPassword)) throw new Error('Invalid master password');
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.url) throw new Error('No active tab');
  const domain = new URL(tab.url).hostname;
  const vault = await storage.loadVault();
  const entry = vault.entries.find(e => {
    try { return new URL(e.url).hostname === domain; } catch { return false; }
  });
  if (!entry) throw new Error('No saved credential for this site');
  const salt = new Uint8Array(base64ToArrayBuffer(vault.masterSalt));
  const key = await deriveKey(masterPassword, salt);
  const plainPassword = await decrypt(entry.iv, entry.ciphertext, key);
  await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: (username, password) => {
      // Heuristic: find first visible password field, then associated username field
      const pwdFields = document.querySelectorAll('input[type="password"]');
      for (const pwd of pwdFields) {
        if (pwd.offsetParent === null) continue; // not visible
        // Try to find a preceding text/email input in the same form
        let userField = null;
        const form = pwd.closest('form');
        if (form) {
          const inputs = form.querySelectorAll('input[type="text"], input[type="email"], input:not([type])');
          for (const inp of inputs) {
            if (inp.offsetParent !== null) {
              userField = inp;
              break;
            }
          }
        }
        if (!userField) {
          // Fallback: look for input right before password
          let prev = pwd.previousElementSibling;
          while (prev) {
            if (prev.tagName === 'INPUT' && (prev.type === 'text' || prev.type === 'email' || !prev.type)) {
              userField = prev;
              break;
            }
            prev = prev.previousElementSibling;
          }
        }
        if (userField) {
          userField.value = username;
          userField.dispatchEvent(new Event('input', { bubbles: true }));
        }
        pwd.value = password;
        pwd.dispatchEvent(new Event('input', { bubbles: true }));
        // Also dispatch change events for frameworks
        if (userField) userField.dispatchEvent(new Event('change', { bubbles: true }));
        pwd.dispatchEvent(new Event('change', { bubbles: true }));
        return;
      }
    },
    args: [entry.username, plainPassword]
  });
}

// Message handler
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (!isExtensionSender(sender)) {
    sendResponse({ success: false, error: 'Unauthorised sender' });
    return true;
  }
  (async () => {
    try {
      switch (request.action) {
        case 'checkExists': {
          const vault = await storage.loadVault();
          sendResponse({ hasMaster: !!vault.masterSalt });
          break;
        }
        case 'createMaster':
          await createMaster(request.password);
          sendResponse({ success: true });
          break;
        case 'unlock': {
          const ok = await verifyMaster(request.password);
          sendResponse({ success: ok });
          break;
        }
        case 'getEntries': {
          const entries = await getEntries(request.password);
          sendResponse({ success: true, entries });
          break;
        }
        case 'decryptPassword': {
          const pwd = await decryptPassword(request.id, request.password);
          sendResponse({ success: true, password: pwd });
          break;
        }
        case 'addEntry': {
          const id = await addEntry(request.url, request.username, request.entryPassword, request.masterPassword);
          sendResponse({ success: true, id });
          break;
        }
        case 'deleteEntry':
          await deleteEntry(request.id, request.password);
          sendResponse({ success: true });
          break;
        case 'autofill':
          await autofill(request.password);
          sendResponse({ success: true });
          break;
        default:
          sendResponse({ success: false, error: 'Unknown action' });
      }
    } catch (err) {
      sendResponse({ success: false, error: err.message });
    }
  })();
  return true; // async sendResponse
});
```

---

## 5. popup.html
```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <link rel="stylesheet" href="popup.css">
</head>
<body>
  <div id="app"></div>
  <script src="popup.js"></script>
</body>
</html>
```

## popup.css (basic)
```css
body { width: 320px; font-family: system-ui, sans-serif; padding: 12px; }
.hidden { display: none; }
.error { color: red; }
input { width: 100%; box-sizing: border-box; margin-bottom: 6px; }
button { margin: 4px 2px; }
```

## popup.js
```javascript
(function() {
  'use strict';
  const app = document.getElementById('app');
  let masterPassword = null; // kept in memory for the popup session only

  function clearUI() { app.innerHTML = ''; }

  function showError(msg) {
    const el = document.createElement('div');
    el.className = 'error';
    el.textContent = msg;
    app.appendChild(el);
  }

  // Generic message sender
  async function sendMessage(action, data = {}) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ action, ...data }, (response) => {
        if (chrome.runtime.lastError) resolve({ success: false, error: "Extension context invalidated" });
        else resolve(response);
      });
    });
  }

  // ----- Setup Master Password -----
  function showSetup() {
    clearUI();
    const heading = document.createElement('h2');
    heading.textContent = 'Set Master Password';
    const pwInput = document.createElement('input');
    pwInput.type = 'password';
    pwInput.placeholder = 'Master password';
    const confirmInput = document.createElement('input');
    confirmInput.type = 'password';
    confirmInput.placeholder = 'Confirm password';
    const btn = document.createElement('button');
    btn.textContent = 'Create Vault';
    btn.onclick = async () => {
      if (pwInput.value !== confirmInput.value) {
        showError('Passwords do not match');
        return;
      }
      const res = await sendMessage('createMaster', { password: pwInput.value });
      if (res.success) {
        masterPassword = pwInput.value;
        showList();
      } else {
        showError(res.error);
      }
    };
    app.append(heading, pwInput, confirmInput, btn);
  }

  // ----- Unlock -----
  function showUnlock() {
    clearUI();
    const heading = document.createElement('h2');
    heading.textContent = 'Unlock Vault';
    const pwInput = document.createElement('input');
    pwInput.type =
