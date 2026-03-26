import type { AIProvider, Message, ProviderOptions, StreamCallbacks } from './types.js';
import { PROVIDER_CONFIGS } from './types.js';

export class OpenAIProvider implements AIProvider {
  name = 'openai';

  async chat(messages: Message[], options: ProviderOptions): Promise<string> {
    const baseUrl = options.baseUrl || PROVIDER_CONFIGS.openai.baseUrl;

    const response = await fetch(`${baseUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${options.apiKey}`,
      },
      body: JSON.stringify({
        model: options.model,
        messages,
        temperature: options.temperature ?? 0.7,
        max_tokens: options.maxTokens,
      }),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`OpenAI API error: ${error}`);
    }

    const data = await response.json();
    return data.choices[0].message.content;
  }

  async stream(
    messages: Message[],
    options: ProviderOptions,
    callbacks: StreamCallbacks
  ): Promise<void> {
    const baseUrl = options.baseUrl || PROVIDER_CONFIGS.openai.baseUrl;

    try {
      const response = await fetch(`${baseUrl}/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${options.apiKey}`,
        },
        body: JSON.stringify({
          model: options.model,
          messages,
          temperature: options.temperature ?? 0.7,
          max_tokens: options.maxTokens,
          stream: true,
        }),
      });

      if (!response.ok) {
        const error = await response.text();
        throw new Error(`OpenAI API error: ${error}`);
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
            if (data === '[DONE]') continue;

            try {
              const parsed = JSON.parse(data);
              const token = parsed.choices[0]?.delta?.content || '';
              if (token) {
                fullResponse += token;
                callbacks.onToken(token);
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

  async listModels(apiKey: string): Promise<string[]> {
    const response = await fetch(`${PROVIDER_CONFIGS.openai.baseUrl}/models`, {
      headers: {
        Authorization: `Bearer ${apiKey}`,
      },
    });

    if (!response.ok) {
      return [...PROVIDER_CONFIGS.openai.models];
    }

    const data = await response.json();
    return data.data
      .filter((m: { id: string }) => m.id.startsWith('gpt'))
      .map((m: { id: string }) => m.id);
  }
}
