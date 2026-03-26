export type User = {
  id: string;
  email: string;
  name: string | null;
  image: string | null;
  createdAt: Date;
  updatedAt: Date;
};

export type Session = {
  id: string;
  userId: string;
  token: string;
  expiresAt: Date;
  createdAt: Date;
};

export type ApiKey = {
  id: string;
  userId: string;
  name: string;
  keyPrefix: string;
  lastUsedAt: Date | null;
  expiresAt: Date | null;
  createdAt: Date;
};

export type Provider = 'openai' | 'anthropic' | 'google' | 'mistral' | 'groq' | 'ollama' | 'custom';

export type ProviderConfig = {
  provider: Provider;
  apiKey: string;
  baseUrl?: string;
  model: string;
  temperature?: number;
  maxTokens?: number;
};

export type Conversation = {
  id: string;
  userId: string;
  title: string;
  provider: Provider;
  model: string;
  createdAt: Date;
  updatedAt: Date;
};

export type Message = {
  id: string;
  conversationId: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  tokens: number;
  createdAt: Date;
};

export type Tool = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
};

export type ToolCall = {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
  result?: string;
};

export type AgentConfig = {
  id: string;
  name: string;
  description: string;
  systemPrompt: string;
  tools: string[];
  provider: Provider;
  model: string;
};

export type DeviceToken = {
  token: string;
  userId: string | null;
  expiresAt: Date;
  verified: boolean;
};
