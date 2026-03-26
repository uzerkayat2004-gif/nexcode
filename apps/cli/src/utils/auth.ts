import { homedir } from 'os';
import { join } from 'path';
import { mkdir, readFile, writeFile, unlink, chmod } from 'fs/promises';
import crypto from 'crypto';

const NEXCODE_DIR = join(homedir(), '.nexcode');
const AUTH_FILE = join(NEXCODE_DIR, 'auth.json');
const API_URL = process.env.NEXCODE_API_URL || 'http://localhost:3000';

export type AuthData = {
  type: 'oauth' | 'api-key';
  email: string;
  apiKey?: string;
  sessionToken?: string;
  userId?: string;
  expiresAt?: string;
};

export function generateDeviceCode(): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
  return Array.from({ length: 8 }, () =>
    chars.charAt(Math.floor(Math.random() * chars.length))
  ).join('-');
}

export async function pollForAuth(
  deviceCode: string,
  timeout = 900000 // 15 minutes
): Promise<AuthData> {
  const startTime = Date.now();
  const pollInterval = 2000; // 2 seconds

  // First, create a device token
  const tokenResponse = await fetch(`${API_URL}/api/auth/device-token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ deviceCode }),
  });

  if (!tokenResponse.ok) {
    throw new Error('Failed to create device token');
  }

  const { token } = await tokenResponse.json();

  while (Date.now() - startTime < timeout) {
    const pollResponse = await fetch(
      `${API_URL}/api/auth/device-poll?token=${token}`
    );

    if (pollResponse.ok) {
      const data = await pollResponse.json();

      if (data.status === 'authorized') {
        return {
          type: 'oauth',
          email: data.email,
          sessionToken: data.sessionToken,
          userId: data.userId,
        };
      }
    }

    await new Promise((resolve) => setTimeout(resolve, pollInterval));
  }

  throw new Error('Authentication timed out');
}

export async function saveAuth(auth: AuthData): Promise<void> {
  await mkdir(NEXCODE_DIR, { recursive: true });

  // Encrypt sensitive data
  const encrypted = encryptData(JSON.stringify(auth));

  await writeFile(AUTH_FILE, encrypted, 'utf-8');

  // Set file permissions to 600 (owner read/write only)
  try {
    await chmod(AUTH_FILE, 0o600);
  } catch {
    // Windows doesn't support chmod the same way
  }
}

export async function getAuth(): Promise<AuthData | null> {
  try {
    const encrypted = await readFile(AUTH_FILE, 'utf-8');
    const decrypted = decryptData(encrypted);
    return JSON.parse(decrypted) as AuthData;
  } catch {
    return null;
  }
}

export async function clearAuth(): Promise<void> {
  try {
    await unlink(AUTH_FILE);
  } catch {
    // File doesn't exist
  }
}

function getEncryptionKey(): Buffer {
  const machineId = process.env.COMPUTERNAME || process.env.HOSTNAME || 'default';
  const salt = 'nexcode-encryption-salt';
  return crypto.pbkdf2Sync(machineId, salt, 100000, 32, 'sha256');
}

function encryptData(data: string): string {
  const key = getEncryptionKey();
  const iv = crypto.randomBytes(16);
  const cipher = crypto.createCipheriv('aes-256-gcm', key, iv);

  let encrypted = cipher.update(data, 'utf-8', 'hex');
  encrypted += cipher.final('hex');

  const authTag = cipher.getAuthTag();

  return JSON.stringify({
    iv: iv.toString('hex'),
    encrypted,
    authTag: authTag.toString('hex'),
  });
}

function decryptData(encryptedJson: string): string {
  const { iv, encrypted, authTag } = JSON.parse(encryptedJson);
  const key = getEncryptionKey();

  const decipher = crypto.createDecipheriv(
    'aes-256-gcm',
    key,
    Buffer.from(iv, 'hex')
  );
  decipher.setAuthTag(Buffer.from(authTag, 'hex'));

  let decrypted = decipher.update(encrypted, 'hex', 'utf-8');
  decrypted += decipher.final('utf-8');

  return decrypted;
}
