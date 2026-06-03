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
---

### 2. `popup.html`
The user interface containing the input form and the list where saved passwords will be displayed.
---

### 3. `popup.css`
Styles the popup to look clean, modern, and compact.
---

### 4. `popup.js`
Handles saving credentials to `chrome.storage.local`, rendering the list, toggling password visibility, copying to clipboard, and deleting entries.
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
