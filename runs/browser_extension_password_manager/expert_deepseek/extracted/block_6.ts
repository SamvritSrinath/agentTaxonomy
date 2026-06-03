// Registration flow for a service (storing a passkey)
export async function registerCredential(
  vaultKey: CryptoKey,
  challenge: Uint8Array,
  rp: PublicKeyCredentialCreationOptions
): Promise<PublicKeyCredential> {
  // Use WebAuthn API to create credential locally.
  // This will prompt for platform authenticator (TouchID, Windows Hello)
  // The private key is stored inside the platform authenticator.
  // We additionally encrypt the credential metadata and store in vault.
  // ...
}

// Using a stored passkey to sign in to a website
export async function getCredential(
  vaultKey: CryptoKey,
  credentialId: Uint8Array,
  challenge: Uint8Array
): Promise<PublicKeyCredential> {
  // Retrieve encrypted credential from vault, decrypt, and use it
  // with navigator.credentials.get()
}
