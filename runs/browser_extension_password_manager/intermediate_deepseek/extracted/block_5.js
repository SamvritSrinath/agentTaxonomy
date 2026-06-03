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
