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
