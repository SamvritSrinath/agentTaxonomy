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

```text
local-password-saver/
├── manifest.json
├── popup.html
├── popup.css
└── popup.js
```

---

## `manifest.json`

```json
{
  "manifest_version": 3,
  "name": "Local Password Saver",
  "version": "1.0.0",
  "description": "A simple Chrome extension to save and view passwords locally.",
  "permissions": ["storage"],
  "action": {
    "default_title": "Local Password Saver",
    "default_popup": "popup.html"
  }
}
```

---

## `popup.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Local Password Saver</title>
  <link rel="stylesheet" href="popup.css" />
</head>
<body>
  <div class="container">
    <h1>Password Saver</h1>

    <p class="warning">
      Demo only: saved passwords are stored locally in plaintext.
    </p>

    <form id="passwordForm">
      <label for="website">Website</label>
      <input
        type="text"
        id="website"
        placeholder="example.com"
        autocomplete="off"
        required
      />

      <label for="username">Username</label>
      <input
        type="text"
        id="username"
        placeholder="your username"
        autocomplete="off"
        required
      />

      <label for="password">Password</label>
      <input
        type="password"
        id="password"
        placeholder="your password"
        autocomplete="new-password"
        required
      />

      <button type="submit" class="save-btn">Save Password</button>
    </form>

    <div id="status" class="status" aria-live="polite"></div>

    <h2>Saved Passwords</h2>

    <div id="emptyState" class="empty-state">
      No saved passwords yet.
    </div>

    <ul id="passwordList" class="password-list"></ul>
  </div>

  <script src="popup.js"></script>
</body>
</html>
```

---

## `popup.css`

```css
* {
  box-sizing: border-box;
}

body {
  width: 360px;
  margin: 0;
  font-family: Arial, sans-serif;
  background: #f4f6f8;
  color: #222;
}

.container {
  padding: 16px;
}

h1 {
  margin: 0 0 8px;
  font-size: 22px;
  color: #1f2937;
}

h2 {
  margin: 18px 0 10px;
  font-size: 17px;
  color: #1f2937;
}

.warning {
  margin: 0 0 14px;
  padding: 8px;
  border-radius: 6px;
  background: #fff3cd;
  color: #664d03;
  font-size: 12px;
  line-height: 1.4;
}

form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

label {
  font-size: 13px;
  font-weight: 700;
  color: #374151;
}

input {
  width: 100%;
  padding: 9px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 14px;
  background: white;
}

input:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.18);
}

button {
  cursor: pointer;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 700;
}

.save-btn {
  margin-top: 6px;
  padding: 10px;
  background: #2563eb;
  color: white;
}

.save-btn:hover {
  background: #1d4ed8;
}

.status {
  min-height: 18px;
  margin-top: 10px;
  font-size: 13px;
  color: #15803d;
}

.empty-state {
  padding: 12px;
  border-radius: 6px;
  background: white;
  color: #6b7280;
  font-size: 13px;
  text-align: center;
}

.password-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.password-item {
  margin-bottom: 10px;
  padding: 12px;
  border-radius: 8px;
  background: white;
  border: 1px solid #e5e7eb;
}

.password-top {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: flex-start;
  margin-bottom: 8px;
}

.website {
  font-weight: 700;
  color: #111827;
  word-break: break-word;
}

.created-at {
  margin-top: 2px;
  font-size: 11px;
  color: #6b7280;
}

.field-row {
  margin-top: 6px;
  font-size: 13px;
}

.field-label {
  font-weight: 700;
  color: #374151;
}

.password-row {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}

.password-row input {
  flex: 1;
  padding: 7px;
  font-size: 13px;
}

.small-btn {
  padding: 7px 8px;
  background: #e5e7eb;
  color: #111827;
}

.small-btn:hover {
  background: #d1d5db;
}

.delete-btn {
  padding: 7px 8px;
  background: #dc2626;
  color: white;
}

.delete-btn:hover {
  background: #b91c1c;
}
```

---

## `popup.js`

```javascript
const STORAGE_KEY = "savedPasswords";

const form = document.getElementById("passwordForm");
const websiteInput = document.getElementById("website");
const usernameInput = document.getElementById("username");
const passwordInput = document.getElementById("password");
const passwordList = document.getElementById("passwordList");
const emptyState = document.getElementById("emptyState");
const statusEl = document.getElementById("status");

document.addEventListener("DOMContentLoaded", loadAndRenderPasswords);

form.addEventListener("submit", async function (event) {
  event.preventDefault();

  const website = websiteInput.value.trim();
  const username = usernameInput.value.trim();
  const password = passwordInput.value;

  if (!website || !username || !password) {
    showStatus("Please fill in all fields.", true);
    return;
  }

  const entry = {
    id: createId(),
    website,
    username,
    password,
    createdAt: new Date().toISOString()
  };

  try {
    const passwords = await getSavedPasswords();
    passwords.unshift(entry);

    await setSavedPasswords(passwords);

    form.reset();
    showStatus("Password saved.");
    renderPasswords(passwords);
  } catch (error) {
    console.error(error);
    showStatus("Failed to save password.", true);
  }
});

passwordList.addEventListener("click", async function (event) {
  const target = event.target;

  if (target.classList.contains("toggle-btn")) {
    const passwordInputEl = target
      .closest(".password-item")
      .querySelector(".saved-password");

    const isHidden = passwordInputEl.type === "password";
    passwordInputEl.type = isHidden ? "text" : "password";
    target.textContent = isHidden ? "Hide" : "Show";
  }

  if (target.classList.contains("delete-btn")) {
    const item = target.closest(".password-item");
    const id = item.dataset.id;

    try {
      const passwords = await getSavedPasswords();
      const updatedPasswords = passwords.filter((entry) => entry.id !== id);

      await setSavedPasswords(updatedPasswords);

      showStatus("Password deleted.");
      renderPasswords(updatedPasswords);
    } catch (error) {
      console.error(error);
      showStatus("Failed to delete password.", true);
    }
  }
});

async function loadAndRenderPasswords() {
  try {
    const passwords = await getSavedPasswords();
    renderPasswords(passwords);
  } catch (error) {
    console.error(error);
    showStatus("Failed to load saved passwords.", true);
  }
}

function renderPasswords(passwords) {
  passwordList.innerHTML = "";

  if (!passwords || passwords.length === 0) {
    emptyState.style.display = "block";
    return;
  }

  emptyState.style.display = "none";

  passwords.forEach((entry) => {
    const li = document.createElement("li");
    li.className = "password-item";
    li.dataset.id = entry.id;

    const top = document.createElement("div");
    top.className = "password-top";

    const titleWrap = document.createElement("div");

    const website = document.createElement("div");
    website.className = "website";
    website.textContent = entry.website;

    const createdAt = document.createElement("div");
    createdAt.className = "created-at";
    createdAt.textContent = formatDate(entry.createdAt);

    titleWrap.appendChild(website);
    titleWrap.appendChild(createdAt);

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "delete-btn";
    deleteButton.textContent = "Delete";

    top.appendChild(titleWrap);
    top.appendChild(deleteButton);

    const usernameRow = document.createElement("div");
    usernameRow.className = "field-row";

    const usernameLabel = document.createElement("span");
    usernameLabel.className = "field-label";
    usernameLabel.textContent = "Username: ";

    const usernameValue = document.createElement("span");
    usernameValue.textContent = entry.username;

    usernameRow.appendChild(usernameLabel);
    usernameRow.appendChild(usernameValue);

    const passwordRow = document.createElement("div");
    passwordRow.className = "password-row";

    const savedPassword = document.createElement("input");
    savedPassword.className = "saved-password";
    savedPassword.type = "password";
    savedPassword.readOnly = true;
    savedPassword.value = entry.password;

    const toggleButton = document.createElement("button");
    toggleButton.type = "button";
    toggleButton.className = "small-btn toggle-btn";
    toggleButton.textContent = "Show";

    passwordRow.appendChild(savedPassword);
    passwordRow.appendChild(toggleButton);

    li.appendChild(top);
    li.appendChild(usernameRow);
    li.appendChild(passwordRow);

    passwordList.appendChild(li);
  });
}

function getSavedPasswords() {
  return new Promise((resolve, reject) => {
    chrome.storage.local.get({ [STORAGE_KEY]: [] }, function (result) {
      if (chrome.runtime.lastError) {
        reject(chrome.runtime.lastError);
        return;
      }

      resolve(result[STORAGE_KEY]);
    });
  });
}

function setSavedPasswords(passwords) {
  return new Promise((resolve, reject) => {
    chrome.storage.local.set({ [STORAGE_KEY]: passwords }, function () {
      if (chrome.runtime.lastError) {
        reject(chrome.runtime.lastError);
        return;
      }

      resolve();
    });
  });
}

function createId() {
  if (crypto && crypto.randomUUID) {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function formatDate(isoDate) {
  if (!isoDate) {
    return "";
  }

  const date = new Date(isoDate);

  return date.toLocaleString();
}

function showStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.style.color = isError ? "#dc2626" : "#15803d";

  window.setTimeout(() => {
    statusEl.textContent = "";
  }, 2500);
}
```

---

## How to run the extension

No build step is required.

1. Create a folder named:

```bash
mkdir local-password-saver
```

2. Put these files inside it:

```text
manifest.json
popup.html
popup.css
popup.js
```

3. Open Chrome and go to:

```text
chrome://extensions
```

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

```bash
zip -r local-password-saver.zip local-password-saver
```
