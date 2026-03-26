export type Message = {
  role: 'user' | 'assistant' | 'system';
  content: string;
};

export type ProviderOptions = {
  apiKey: string;
  model: string;
  baseUrl?: string;
  temperature?: number;
  maxTokens?: number;
};

export type StreamCallbacks = {
  onToken: (token: string) => void;
  onComplete: (fullResponse: string) => void;
  onError: (error: Error) => void;
};

export interface AIProvider {
  name: string;
  chat(messages: Message[], options: ProviderOptions): Promise<string>;
  stream(messages: Message[], options: ProviderOptions, callbacks: StreamCallbacks): Promise<void>;
  listModels(apiKey: string): Promise<string[]>;
}

export const PROVIDER_CONFIGS = {
  openai: {
    name: 'OpenAI',
    baseUrl: 'https://api.openai.com/v1',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo'],
  },
  anthropic: {
    name: 'Anthropic',
    baseUrl: 'https://api.anthropic.com/v1',
    models: ['claude-3-5-sonnet-20241022', 'claude-3-5-haiku-20241022', 'claude-3-opus-20240229'],
  },
  google: {
    name: 'Google',
    baseUrl: 'https://generativelanguage.googleapis.com/v1beta',
    models: ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-2.0-flash-exp'],
  },
  mistral: {
    name: 'Mistral',
    baseUrl: 'https://api.mistral.ai/v1',
    models: ['mistral-large-latest', 'mistral-medium-latest', 'mistral-small-latest'],
  },
  groq: {
    name: 'Groq',
    baseUrl: 'https://api.groq.com/openai/v1',
    models: ['llama-3.1-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768'],
  },
  ollama: {
    name: 'Ollama',
    baseUrl: 'http://localhost:11434/v1',
    models: ['llama3.1', 'codellama', 'mistral'],
  },
} as const;

export type ProviderName = keyof typeof PROVIDER_CONFIGS;
