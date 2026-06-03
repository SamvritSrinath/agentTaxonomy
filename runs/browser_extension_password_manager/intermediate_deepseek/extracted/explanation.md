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
---

## 2. aes.js (Encryption Utilities)
*Note:* We'll use `importScripts` in the background worker, so we don't need ES module exports in the final code – we'll convert to global functions. The snippet above uses `export` for illustration; the actual `aes.js` will attach to `self`.

### (adjusted aes.js for service worker)
---

## 3. storage.js
---

## 4. background.js (Service Worker)
---

## 5. popup.html
## popup.css (basic)
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
