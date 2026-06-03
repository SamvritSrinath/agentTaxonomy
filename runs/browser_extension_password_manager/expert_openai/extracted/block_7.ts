import { describe, expect, it } from "vitest";
import { decryptJson, encryptJson, VaultRecord } from "./index";

describe("vault crypto", () => {
  it("encrypts and decrypts vault data", async () => {
    const vault: VaultRecord[] = [
      {
        id: "1",
        origin: "https://example.com",
        username: "alice",
        password: "correct-horse-battery-staple",
        updatedAt: new Date().toISOString()
      }
    ];

    const encrypted = await encryptJson(vault, "master password");
    expect(encrypted.ciphertextB64).not.toContain("correct-horse");

    const decrypted = await decryptJson<VaultRecord[]>(encrypted, "master password");
    expect(decrypted[0]?.username).toBe("alice");
  });

  it("fails on wrong master secret", async () => {
    const encrypted = await encryptJson([{ secret: "value" }], "right");
    await expect(decryptJson(encrypted, "wrong")).rejects.toThrow();
  });
});
