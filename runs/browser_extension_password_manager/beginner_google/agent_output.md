Here is a complete, fully functional Chrome extension built using **Manifest V3** that allows users to save, view, copy, and delete passwords locally. 

For security, this extension uses Chrome's secure local storage (`chrome.storage.local`). *Note: In a production environment, passwords should be encrypted before saving; this version stores them in plaintext for simplicity and educational purposes.*

---

### File Structure
Create a new folder (e.g., `simple-password-manager`) and place the following four files inside it:
1. `manifest.json`
2. `popup.html`
3. `popup.css`
4. `popup.js`

---

### 1. `manifest.json`
This file registers the extension with Chrome, requests storage permissions, and defines the popup window.

```json
{
  "manifest_version": 3,
  "name": "Simple Password Manager",
  "version": "1.0",
  "description": "A simple extension to save and manage your passwords locally.",
  "permissions": [
    "storage"
  ],
  "action": {
    "default_popup": "popup.html"
  }
}
```

---

### 2. `popup.html`
The user interface containing the input form and the list where saved passwords will be displayed.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Password Manager</title>
  <link rel="stylesheet" href="popup.css">
</head>
<body>
  <div class="container">
    <h2>🔑 Password Manager</h2>
    
    <!-- Input Form -->
    <form id="password-form">
      <div class="input-group">
        <label for="website">Website / App</label>
        <input type="text" id="website" placeholder="e.g., github.com" required />
      </div>
      <div class="input-group">
        <label for="username">Username / Email</label>
        <input type="text" id="username" placeholder="e.g., user@example.com" required />
      </div>
      <div class="input-group">
        <label for="password">Password</label>
        <input type="password" id="password" placeholder="••••••••" required />
      </div>
      <button type="submit" class="btn-save">Save Password</button>
    </form>

    <hr />

    <!-- Search Bar -->
    <input type="text" id="search" placeholder="🔍 Search saved passwords..." />

    <!-- Saved Passwords List -->
    <h3>Saved Credentials</h3>
    <div id="password-list" class="password-list">
      <p class="empty-state">No passwords saved yet.</p>
    </div>
  </div>

  <script src="popup.js"></script>
</body>
</html>
```

---

### 3. `popup.css`
Styles the popup to look clean, modern, and compact.

```css
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  width: 350px;
  margin: 0;
  padding: 15px;
  background-color: #f8f9fa;
  color: #333;
}

.container {
  display: flex;
  flex-direction: column;
}

h2 {
  margin-top: 0;
  margin-bottom: 15px;
  font-size: 1.2rem;
  text-align: center;
  color: #2c3e50;
}

h3 {
  font-size: 1rem;
  margin: 15px 0 8px 0;
  color: #2c3e50;
}

hr {
  border: 0;
  border-top: 1px solid #e2e8f0;
  margin: 15px 0;
}

.input-group {
  margin-bottom: 10px;
  display: flex;
  flex-direction: column;
}

.input-group label {
  font-size: 0.75rem;
  font-weight: 600;
  margin-bottom: 4px;
  color: #4a5568;
}

input {
  padding: 8px 10px;
  border: 1px solid #cbd5e0;
  border-radius: 6px;
  font-size: 0.85rem;
  outline: none;
  transition: border-color 0.2s;
}

input:focus {
  border-color: #3182ce;
}

#search {
  width: calc(100% - 22px);
  margin-bottom: 10px;
}

.btn-save {
  width: 100%;
  padding: 10px;
  background-color: #3182ce;
  color: white;
  border: none;
  border-radius: 6px;
  font-weight: bold;
  cursor: pointer;
  font-size: 0.85rem;
  transition: background-color 0.2s;
}

.btn-save:hover {
  background-color: #2b6cb0;
}

/* Password List Styles */
.password-list {
  max-height: 220px;
  overflow-y: auto;
}

.empty-state {
  text-align: center;
  color: #a0aec0;
  font-size: 0.85rem;
  margin: 20px 0;
}

.password-card {
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.card-title {
  font-weight: bold;
  font-size: 0.9rem;
  color: #2d3748;
}

.card-body {
  font-size: 0.8rem;
  color: #4a5568;
  line-height: 1.4;
}

.card-actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
  margin-top: 8px;
}

.btn-action {
  padding: 4px 8px;
  font-size: 0.75rem;
  border: 1px solid #cbd5e0;
  border-radius: 4px;
  background: white;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-action:hover {
  background: #edf2f7;
}

.btn-delete {
  color: #e53e3e;
  border-color: #fed7d7;
}

.btn-delete:hover {
  background: #fff5f5;
}
```

---

### 4. `popup.js`
Handles saving credentials to `chrome.storage.local`, rendering the list, toggling password visibility, copying to clipboard, and deleting entries.

```javascript
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('password-form');
  const websiteInput = document.getElementById('website');
  const usernameInput = document.getElementById('username');
  const passwordInput = document.getElementById('password');
  const passwordList = document.getElementById('password-list');
  const searchInput = document.getElementById('search');

  // Load and render saved passwords on startup
  loadPasswords();

  // Handle Form Submission
  form.addEventListener('submit', (e) => {
    e.preventDefault();

    const newCredential = {
      id: Date.now().toString(),
      website: websiteInput.value.trim(),
      username: usernameInput.value.trim(),
      password: passwordInput.value
    };

    chrome.storage.local.get({ credentials: [] }, (data) => {
      const credentials = data.credentials;
      credentials.push(newCredential);

      chrome.storage.local.set({ credentials }, () => {
        form.reset();
        loadPasswords();
      });
    });
  });

  // Handle Search Input
  searchInput.addEventListener('input', () => {
    loadPasswords(searchInput.value.trim().toLowerCase());
  });

  // Load passwords from local storage
  function loadPasswords(filter = '') {
    chrome.storage.local.get({ credentials: [] }, (data) => {
      const credentials = data.credentials;
      renderCredentials(credentials, filter);
    });
  }

  // Render credentials to the UI
  function renderCredentials(credentials, filter = '') {
    passwordList.innerHTML = '';

    const filtered = credentials.filter(item => 
      item.website.toLowerCase().includes(filter) || 
      item.username.toLowerCase().includes(filter)
    );

    if (filtered.length === 0) {
      passwordList.innerHTML = `<p class="empty-state">${filter ? 'No matches found.' : 'No passwords saved yet.'}</p>`;
      return;
    }

    filtered.forEach(item => {
      const card = document.createElement('div');
      card.className = 'password-card';
      card.innerHTML = `
        <div class="card-header">
          <span class="card-title">${escapeHtml(item.website)}</span>
        </div>
        <div class="card-body">
          <div><strong>User:</strong> ${escapeHtml(item.username)}</div>
          <div>
            <strong>Pass:</strong> 
            <span class="masked-pass" id="pass-${item.id}">••••••••</span>
            <span class="raw-pass" id="raw-${item.id}" style="display: none;">${escapeHtml(item.password)}</span>
          </div>
        </div>
        <div class="card-actions">
          <button class="btn-action btn-toggle" data-id="${item.id}">Show</button>
          <button class="btn-action btn-copy" data-pass="${escapeHtml(item.password)}">Copy</button>
          <button class="btn-action btn-delete" data-id="${item.id}">Delete</button>
        </div>
      `;

      passwordList.appendChild(card);
    });

    attachCardEventListeners();
  }

  // Attach event listeners to dynamically generated buttons
  function attachCardEventListeners() {
    // Toggle Password Visibility
    document.querySelectorAll('.btn-toggle').forEach(button => {
      button.addEventListener('click', (e) => {
        const id = e.target.getAttribute('data-id');
        const maskedSpan = document.getElementById(`pass-${id}`);
        const rawSpan = document.getElementById(`raw-${id}`);

        if (rawSpan.style.display === 'none') {
          rawSpan.style.display = 'inline';
          maskedSpan.style.display = 'none';
          e.target.textContent = 'Hide';
        } else {
          rawSpan.style.display = 'none';
          maskedSpan.style.display = 'inline';
          e.target.textContent = 'Show';
        }
      });
    });

    // Copy Password to Clipboard
    document.querySelectorAll('.btn-copy').forEach(button => {
      button.addEventListener('click', (e) => {
        const password = e.target.getAttribute('data-pass');
        navigator.clipboard.writeText(password).then(() => {
          const originalText = e.target.textContent;
          e.target.textContent = 'Copied!';
          e.target.style.borderColor = '#48bb78';
          e.target.style.color = '#48bb78';
          setTimeout(() => {
            e.target.textContent = originalText;
            e.target.style.borderColor = '';
            e.target.style.color = '';
          }, 1500);
        });
      });
    });

    // Delete Password Entry
    document.querySelectorAll('.btn-delete').forEach(button => {
      button.addEventListener('click', (e) => {
        const id = e.target.getAttribute('data-id');
        if (confirm('Are you sure you want to delete this password?')) {
          chrome.storage.local.get({ credentials: [] }, (data) => {
            const updatedCredentials = data.credentials.filter(item => item.id !== id);
            chrome.storage.local.set({ credentials: updatedCredentials }, () => {
              loadPasswords(searchInput.value.trim().toLowerCase());
            });
          });
        }
      });
    });
  }

  // Helper function to prevent XSS
  function escapeHtml(str) {
    return str.replace(/&/g, "&amp;")
              .replace(/</g, "&lt;")
              .replace(/>/g, "&gt;")
              .replace(/"/g, "&quot;")
              .replace(/'/g, "&#039;");
  }
});
```

---

### How to Install and Run the Extension

1. Open your Google Chrome browser.
2. Navigate to the Extensions page by typing `chrome://extensions/` in the URL bar and pressing Enter.
3. In the top-right corner of the Extensions page, toggle the **Developer mode** switch to **ON**.
4. In the top-left corner, click the **Load unpacked** button.
5. Select the folder (`simple-password-manager`) containing the four files you created.
6. The extension is now installed! Click the puzzle piece icon (Extensions menu) in your Chrome toolbar, find **Simple Password Manager**, and pin it for easy access.

---

### How it Works
* **Manifest V3**: Uses the latest Chrome Extension standard.
* **`chrome.storage.local`**: Safely saves your credentials directly inside Chrome's local sandbox. The data persists even if you close Chrome or restart your computer.
* **Dynamic UI**: Includes a search bar to filter saved credentials instantly, a "Show/Hide" toggle to view passwords, a "Copy" button that interacts with your system clipboard, and a "Delete" button to clean up entries.
