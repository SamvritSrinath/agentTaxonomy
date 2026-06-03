Below is a complete simple Chrome Extension using Manifest V3.

It includes:

- Popup UI
- Website / username / password inputs
- Local saving with `chrome.storage.local`
- Saved password list
- Show/hide password
- Delete saved entries

> Note: This stores passwords locally in plaintext inside Chrome extension storage. It is okay for a demo, but not secure enough for real password management.

---

## File structure
---

## `manifest.json`
---

## `popup.html`
---

## `popup.css`
---

## `popup.js`
---

## How to run the extension

No build step is required.

1. Create a folder named:
2. Put these files inside it:
3. Open Chrome and go to:
4. Enable **Developer mode**.

5. Click **Load unpacked**.

6. Select the `local-password-saver` folder.

7. Click the extension icon to open the popup.

---

## Manual tests

### Test 1: Save a password

1. Open the popup.
2. Enter:
   - Website: `example.com`
   - Username: `alice`
   - Password: `mySecret123`
3. Click **Save Password**.
4. Confirm the password appears in the saved list.

Expected result: The saved entry appears with website, username, and a hidden password field.

---

### Test 2: Show and hide a password

1. Save a password.
2. Click **Show**.

Expected result: The password becomes visible and the button changes to **Hide**.

3. Click **Hide**.

Expected result: The password is hidden again.

---

### Test 3: Persistence

1. Save a password.
2. Close the popup.
3. Open the popup again.

Expected result: The saved password is still listed.

---

### Test 4: Delete a password

1. Save a password.
2. Click **Delete**.

Expected result: The password is removed from the list.

---

## Packaging command, optional

If you want to zip the extension folder:
