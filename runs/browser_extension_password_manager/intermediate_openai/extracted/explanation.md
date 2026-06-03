Below is a production-style Manifest V3 Chrome extension password manager implemented in TypeScript.

It includes:

- Secure local vault storage using `chrome.storage.local`
- AES-256-GCM encryption via WebCrypto
- PBKDF2 master-password key derivation
- Master password setup/unlock/lock flow
- User-triggered autofill for detected login forms
- Strict message validation and origin checks
- No `innerHTML`, no remote code, strict CSP
- Tests for crypto behavior

---

## Project structure
---

## `package.json`
---

## `tsconfig.json`
---

## `manifest.json`
---

## `scripts/copy-static.mjs`
---

## `src/types.ts`
---

## `src/crypto.ts`
---

## `src/storage.ts`
---

## `src/background.ts`
---

## `src/content.ts`

```ts
function isVisibleInput(input: HTMLInputElement): boolean {
  if (input.disabled || input.readOnly) return false;

  const style = window.getComputedStyle(input);

  if (
    style.display === "none" ||
    style.visibility === "hidden" ||
    style.opacity === "0"
  ) {
    return false;
  }

  const rect = input.getBoundingClientRect();

  return rect.width > 0 && rect.height > 0;
}

function hasPasswordForm(): boolean {
  return [...document.querySelectorAll("input[type='password']")].some(
    (input) => input instanceof HTMLInput
