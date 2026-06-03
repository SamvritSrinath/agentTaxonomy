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
