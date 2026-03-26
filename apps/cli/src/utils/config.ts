import { homedir } from 'os';
import { join } from 'path';
import { mkdir, readFile, writeFile } from 'fs/promises';

const NEXCODE_DIR = join(homedir(), '.nexcode');
const CONFIG_FILE = join(NEXCODE_DIR, 'config.json');

export type Config = {
  defaultProvider?: string;
  defaultModel?: string;
  theme?: 'dark' | 'light';
  editor?: string;
  [key: string]: string | undefined;
};

async function ensureConfigDir(): Promise<void> {
  await mkdir(NEXCODE_DIR, { recursive: true });
}

async function loadConfig(): Promise<Config> {
  try {
    const data = await readFile(CONFIG_FILE, 'utf-8');
    return JSON.parse(data) as Config;
  } catch {
    return {};
  }
}

async function saveConfig(config: Config): Promise<void> {
  await ensureConfigDir();
  await writeFile(CONFIG_FILE, JSON.stringify(config, null, 2), 'utf-8');
}

export async function getConfig(key: string): Promise<string | undefined> {
  const config = await loadConfig();
  return config[key];
}

export async function setConfig(key: string, value: string): Promise<void> {
  const config = await loadConfig();
  config[key] = value;
  await saveConfig(config);
}

export async function listConfig(): Promise<Config> {
  return loadConfig();
}

export async function getProjectConfig(): Promise<Config> {
  const cwd = process.cwd();
  const configFile = join(cwd, '.nexcode', 'config.json');

  try {
    const data = await readFile(configFile, 'utf-8');
    return JSON.parse(data) as Config;
  } catch {
    return {};
  }
}
