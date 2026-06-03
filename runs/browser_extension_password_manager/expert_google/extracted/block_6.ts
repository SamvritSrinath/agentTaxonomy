// Content script for secure autofill and credential detection
console.log('[SecureVault] Content script active');

// Listen for messages from the background script or popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'AUTOFILL_CREDENTIALS') {
    const { username, password } = request.payload;
    const usernameField = document.querySelector('input[type="email"], input[type="text"]') as HTMLInputElement;
    const passwordField = document.querySelector('input[type="password"]') as HTMLInputElement;

    if (usernameField && passwordField) {
      usernameField.value = username;
      passwordField.value = password;
      
      // Dispatch input events to trigger React/Angular/Vue state updates
      usernameField.dispatchEvent(new Event('input', { bubbles: true }));
      passwordField.dispatchEvent(new Event('input', { bubbles: true }));
      
      sendResponse({ success: true });
    } else {
      sendResponse({ success: false, error: 'Fields not found' });
    }
  }
});
