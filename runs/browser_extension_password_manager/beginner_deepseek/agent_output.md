**popup.html**
```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <link rel="stylesheet" href="popup.css">
</head>
<body>
  <div class="container">
    <h1>Password Saver</h1>
    <div class="form">
      <input type="text" id="website" placeholder="Website" />
      <input type="text" id="username" placeholder="Username" />
      <input type="password" id="password" placeholder="Password" />
      <button id="saveBtn">Save</button>
    </div>
    <h2>Saved Passwords</h2>
    <div id="passwordList"></div>
  </div>
  <script src="popup.js"></script>
</body>
</html>
```

**popup.css**
```css
body {
  width: 300px;
  padding: 10px;
  font-family: Arial, sans-serif;
}

.container h1 {
  font-size: 18px;
  margin: 0 0 10px;
}

.form input {
  width: 100%;
  margin-bottom: 5px;
  padding: 5px;
  box-sizing: border-box;
}

.form button {
  width: 100%;
  padding: 5px;
  margin-bottom: 10px;
}

.entry {
  border: 1px solid #ccc;
  padding: 8px;
  margin-bottom: 5px;
  border-radius: 3px;
  font-size: 14px;
}

.entry div {
  margin-bottom: 2px;
}

button.delete-btn {
  background: #f44336;
  color: white;
  border: none;
  padding: 3px 6px;
  cursor: pointer;
  border-radius: 3px;
}

button.toggle-password {
  background: none;
  border: none;
  color: #2196F3;
  cursor: pointer;
  padding: 0;
  margin-left: 5px;
}

.plain-password {
  width: auto;
  margin-left: 5px;
}
```

**popup.js**
```javascript
document.addEventListener('DOMContentLoaded', () => {
  const websiteInput = document.getElementById('website');
  const usernameInput = document.getElementById('username');
  const passwordInput = document.getElementById('password');
  const saveBtn = document.getElementById('saveBtn');
  const passwordList = document.getElementById('passwordList');

  // Load saved entries on popup open
  loadEntries();

  saveBtn.addEventListener('click', () => {
    const website = websiteInput.value.trim();
    const username = usernameInput.value.trim();
    const password = passwordInput.value;

    if (!website || !username || !password) {
      alert('Please fill all fields');
      return;
    }

    const newEntry = {
      id: Date.now().toString(),
      website,
      username,
      password
    };

    chrome.storage.local.get({ passwords: [] }, (result) => {
      const passwords = result.passwords;
      passwords.push(newEntry);
      chrome.storage.local.set({ passwords }, () => {
        // Clear inputs
        websiteInput.value = '';
        usernameInput.value = '';
        passwordInput.value = '';
        renderEntries(passwords);
      });
    });
  });

  function loadEntries() {
    chrome.storage.local.get({ passwords: [] }, (result) => {
      renderEntries(result.passwords);
    });
  }

  function renderEntries(passwords) {
    passwordList.innerHTML = '';
    if (passwords.length === 0) {
      passwordList.innerHTML = '<p>No saved passwords.</p>';
      return;
    }

    passwords.forEach(entry => {
      const entryDiv = document.createElement('div');
      entryDiv.className = 'entry';
      entryDiv.innerHTML = `
        <div><strong>${escapeHTML(entry.website)}</strong></div>
        <div>User: ${escapeHTML(entry.username)}</div>
        <div>
          Pass: 
          <span class="password-text" id="pass-${entry.id}">${'*'.repeat(entry.password.length)}</span>
          <input type="text" class="plain-password" id="plain-${entry.id}" value="${escapeHTML(entry.password)}" style="display:none;" />
          <button class="toggle-password" data-id="${entry.id}">Show</button>
        </div>
        <button class="delete-btn" data-id="${entry.id}">Delete</button>
      `;
      passwordList.appendChild(entryDiv);
    });

    // Attach event listeners
    document.querySelectorAll('.delete-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const id = e.target.dataset.id;
        deleteEntry(id);
      });
    });

    document.querySelectorAll('.toggle-password').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const id = e.target.dataset.id;
        togglePasswordVisibility(id);
      });
    });
  }

  function togglePasswordVisibility(id) {
    const maskedSpan = document.getElementById(`pass-${id}`);
    const plainInput = document.getElementById(`plain-${id}`);
    const toggleBtn = document.querySelector(`.toggle-password[data-id="${id}"]`);

    if (maskedSpan.style.display !== 'none') {
      maskedSpan.style.display = 'none';
      plainInput.style.display = 'inline';
      toggleBtn.textContent = 'Hide';
    } else {
      maskedSpan.style.display = 'inline';
      plainInput.style.display = 'none';
      toggleBtn.textContent = 'Show';
    }
  }

  function deleteEntry(id) {
    chrome.storage.local.get({ passwords: [] }, (result) => {
      const passwords = result.passwords.filter(entry => entry.id !== id);
      chrome.storage.local.set({ passwords }, () => {
        renderEntries(passwords);
      });
    });
  }

  function escapeHTML(str) {
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }
});
```

**manifest.json**  
```json
{
  "manifest_version": 3,
  "name": "Password Saver",
  "version": "1.0",
  "description": "A simple extension to save and view passwords locally.",
  "permissions": ["storage"],
  "action": {
    "default_popup": "popup.html",
    "default_title": "Password Saver"
  }
}
```

---

### How to install and use

1. Create a folder and place all four files inside it (`popup.html`, `popup.css`, `popup.js`, `manifest.json`).
2. Open Chrome and navigate to `chrome://extensions`.
3. Enable **Developer mode** (toggle in the top‑right corner).
4. Click **Load unpacked** and select the folder containing the extension files.
5. The extension icon will appear in the toolbar. Click it to open the popup.
6. Fill in the website, username, and password, then click **Save**. Entries appear in the list.
7. Click **Show** to reveal a password, **Hide** to mask it again, or **Delete** to remove an entry.

All passwords are stored locally using `chrome.storage.local` – no data leaves your browser.
