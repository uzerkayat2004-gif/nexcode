import type { AIProvider, Message, ProviderOptions, StreamCallbacks } from './types.js';
import { PROVIDER_CONFIGS } from './types.js';

export class AnthropicProvider implements AIProvider {
  name = 'anthropic';

  async chat(messages: Message[], options: ProviderOptions): Promise<string> {
    const baseUrl = options.baseUrl || PROVIDER_CONFIGS.anthropic.baseUrl;

    const systemMessage = messages.find((m) => m.role === 'system');
    const userMessages = messages.filter((m) => m.role !== 'system');

    const response = await fetch(`${baseUrl}/messages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': options.apiKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: options.model,
        messages: userMessages,
        system: systemMessage?.content,
        temperature: options.temperature ?? 0.7,
        max_tokens: options.maxTokens ?? 4096,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Anthropic API error: ${error}`);
    }

    const data = await response.json();
    return data.content[0].text;
  }

  async stream(
    messages: Message[],
    options: ProviderOptions,
    callbacks: StreamCallbacks
  ): Promise<void> {
    const baseUrl = options.baseUrl || PROVIDER_CONFIGS.anthropic.baseUrl;

    const systemMessage = messages.find((m) => m.role === 'system');
    const userMessages = messages.filter((m) => m.role !== 'system');

    try {
      const response = await fetch(`${baseUrl}/messages`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'x-api-key': options.apiKey,
          'anthropic-version': '2023-06-01',
        },
        body: JSON.stringify({
          model: options.model,
          messages: userMessages,
          system: systemMessage?.content,
          temperature: options.temperature ?? 0.7,
          max_tokens: options.maxTokens ?? 4096,
          stream: true,
        }),
      });

      if (!response.ok) {
        const error = await response.text();
        throw new Error(`Anthropic API error: ${error}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      let fullResponse = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = new TextDecoder().decode(value);
        const lines = text.split('\n').filter((line) => line.trim());

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            try {
              const parsed = JSON.parse(data);
              if (parsed.type === 'content_block_delta' && parsed.delta?.text) {
                fullResponse += parsed.delta.text;
                callbacks.onToken(parsed.delta.text);
              }
            } catch {
              // Skip invalid JSON
            }
          }
        }
      }

      callbacks.onComplete(fullResponse);
    } catch (error) {
      callbacks.onError(error as Error);
    }
  }

  async listModels(_apiKey: string): Promise<string[]> {
    return [...PROVIDER_CONFIGS.anthropic.models];
  }
}
