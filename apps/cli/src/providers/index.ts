import type { AIProvider, Message, ProviderOptions, StreamCallbacks } from './types.js';
import type { ProviderName } from './types.js';
import { PROVIDER_CONFIGS } from './types.js';
import { OpenAIProvider } from './openai.js';
import { AnthropicProvider } from './anthropic.js';

const providers: Record<ProviderName, AIProvider> = {
  openai: new OpenAIProvider(),
  anthropic: new AnthropicProvider(),
  google: new OpenAIProvider(), // Uses OpenAI-compatible API
  mistral: new OpenAIProvider(), // Uses OpenAI-compatible API
  groq: new OpenAIProvider(), // Uses OpenAI-compatible API
  ollama: new OpenAIProvider(), // Uses OpenAI-compatible API
};

export function getProvider(name: ProviderName): AIProvider {
  const provider = providers[name];
  if (!provider) {
    throw new Error(`Unknown provider: ${name}`);
  }
  return provider;
}

export function listProviders(): ProviderName[] {
  return Object.keys(PROVIDER_CONFIGS) as ProviderName[];
}

export function getProviderConfig(name: ProviderName) {
  return PROVIDER_CONFIGS[name];
}

export async function chatWithProvider(
  providerName: ProviderName,
  messages: Message[],
  options: ProviderOptions
): Promise<string> {
  const provider = getProvider(providerName);
  return provider.chat(messages, options);
}

export async function streamWithProvider(
  providerName: ProviderName,
  messages: Message[],
  options: ProviderOptions,
  callbacks: StreamCallbacks
): Promise<void> {
  const provider = getProvider(providerName);
  return provider.stream(messages, options, callbacks);
}

export async function listProviderModels(
  providerName: ProviderName,
  apiKey: string
): Promise<string[]> {
  const provider = getProvider(providerName);
  return provider.listModels(apiKey);
}
