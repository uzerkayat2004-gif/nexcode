import { z } from 'zod';

export const ProviderSchema = z.enum([
  'openai',
  'anthropic',
  'google',
  'mistral',
  'groq',
  'ollama',
  'custom',
]);

export const ProviderConfigSchema = z.object({
  provider: ProviderSchema,
  apiKey: z.string().min(1),
  baseUrl: z.string().url().optional(),
  model: z.string().min(1),
  temperature: z.number().min(0).max(2).optional(),
  maxTokens: z.number().min(1).optional(),
});

export const MessageRoleSchema = z.enum(['user', 'assistant', 'system']);

export const MessageSchema = z.object({
  id: z.string().uuid(),
  conversationId: z.string().uuid(),
  role: MessageRoleSchema,
  content: z.string(),
  tokens: z.number().min(0),
  createdAt: z.date(),
});

export const ConversationSchema = z.object({
  id: z.string().uuid(),
  userId: z.string().uuid(),
  title: z.string().min(1),
  provider: ProviderSchema,
  model: z.string().min(1),
  createdAt: z.date(),
  updatedAt: z.date(),
});

export const UserSchema = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  name: z.string().nullable(),
  image: z.string().url().nullable(),
  createdAt: z.date(),
  updatedAt: z.date(),
});

export const ApiKeySchema = z.object({
  id: z.string().uuid(),
  userId: z.string().uuid(),
  name: z.string().min(1).max(100),
  keyPrefix: z.string().length(8),
  lastUsedAt: z.date().nullable(),
  expiresAt: z.date().nullable(),
  createdAt: z.date(),
});

export const DeviceTokenSchema = z.object({
  token: z.string().min(1),
  userId: z.string().uuid().nullable(),
  expiresAt: z.date(),
  verified: z.boolean(),
});

export const ToolCallSchema = z.object({
  id: z.string(),
  name: z.string(),
  arguments: z.record(z.unknown()),
  result: z.string().optional(),
});

export const AgentConfigSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1),
  description: z.string(),
  systemPrompt: z.string(),
  tools: z.array(z.string()),
  provider: ProviderSchema,
  model: z.string().min(1),
});

export const LoginRequestSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8).optional(),
  provider: z.enum(['google', 'github', 'email']).optional(),
});

export const ApiKeyAuthSchema = z.object({
  apiKey: z.string().startsWith('nxc_sk_'),
});

export const DeviceAuthRequestSchema = z.object({
  deviceCode: z.string().min(1),
});
