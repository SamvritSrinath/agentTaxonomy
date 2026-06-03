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
