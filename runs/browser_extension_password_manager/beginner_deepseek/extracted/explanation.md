**popup.html**
**popup.css**
**popup.js**
**manifest.json**
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
