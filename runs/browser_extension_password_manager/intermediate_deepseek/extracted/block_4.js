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
