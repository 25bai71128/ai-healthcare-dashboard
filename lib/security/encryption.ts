import crypto from "node:crypto";

const ALGO = "aes-256-gcm";
const IV_LENGTH = 12;

function getKey(): Buffer {
  const key = process.env.FIELD_ENCRYPTION_KEY?.trim();
  if (!key) {
    throw new Error("FIELD_ENCRYPTION_KEY is required for encrypted fields.");
  }

  const decoded = Buffer.from(key, "base64");
  if (decoded.length !== 32) {
    throw new Error("FIELD_ENCRYPTION_KEY must be a base64-encoded 32-byte key.");
  }
  return decoded;
}

export function encryptField(input: string | null | undefined): string | null {
  if (!input) return null;

  const iv = crypto.randomBytes(IV_LENGTH);
  const cipher = crypto.createCipheriv(ALGO, getKey(), iv);

  const encrypted = Buffer.concat([cipher.update(input, "utf8"), cipher.final()]);
  const tag = cipher.getAuthTag();

  return `${iv.toString("base64")}.${tag.toString("base64")}.${encrypted.toString("base64")}`;
}

export function decryptField(payload: string | null | undefined): string | null {
  if (!payload) return null;

  const parts = payload.split(".");
  if (parts.length !== 3) {
    return payload;
  }

  const [ivPart, tagPart, cipherPart] = parts;
  const iv = Buffer.from(ivPart, "base64");
  const tag = Buffer.from(tagPart, "base64");
  const encrypted = Buffer.from(cipherPart, "base64");

  const decipher = crypto.createDecipheriv(ALGO, getKey(), iv);
  decipher.setAuthTag(tag);

  const decrypted = Buffer.concat([decipher.update(encrypted), decipher.final()]);
  return decrypted.toString("utf8");
}
