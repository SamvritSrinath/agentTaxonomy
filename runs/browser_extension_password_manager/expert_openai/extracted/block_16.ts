type FillMessage = {
  type: "PM_FILL";
  origin: string;
  username: string;
  password: string;
};

chrome.runtime.onMessage.addListener((msg: FillMessage) => {
  if (msg.type !== "PM_FILL") return;

  if (location.origin !== new URL(msg.origin).origin) {
    return;
  }

  const passwordInput = findPasswordInput();
  if (!passwordInput) return;

  const form = passwordInput.closest("form") ?? document;
  const usernameInput = findUsernameInput(form);

  if (usernameInput) setNativeValue(usernameInput, msg.username);
  setNativeValue(passwordInput, msg.password);
});

function findPasswordInput(): HTMLInputElement | null {
  return document.querySelector<HTMLInputElement>('input[type="password"]');
}

function findUsernameInput(root: ParentNode): HTMLInputElement | null {
  return (
    root.querySelector<HTMLInputElement>('input[autocomplete="username"]') ??
    root.querySelector<HTMLInputElement>('input[type="email"]') ??
    root.querySelector<HTMLInputElement>('input[type="text"]')
  );
}

function setNativeValue(input: HTMLInputElement, value: string) {
  const descriptor = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype,
    "value"
  );

  descriptor?.set?.call(input, value);

  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}
