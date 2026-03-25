import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fetchProviders, ProviderInfo } from './api';

describe('fetchProviders', () => {
    beforeEach(() => {
        // Clear all mocks before each test
        vi.restoreAllMocks();
    });

    it('should correctly fetch and return providers data', async () => {
        // Arrange
        const mockProviders: ProviderInfo[] = [
            { id: 'anthropic', name: 'Anthropic', description: 'Anthropic Claude models', models: ['claude-3-opus-20240229'] },
            { id: 'openai', name: 'OpenAI', description: 'OpenAI GPT models', models: ['gpt-4o', 'gpt-3.5-turbo'] }
        ];

        // Mock the global fetch API
        global.fetch = vi.fn().mockResolvedValue({
            json: vi.fn().mockResolvedValue(mockProviders),
        });

        // Act
        const providers = await fetchProviders();

        // Assert
        expect(global.fetch).toHaveBeenCalledTimes(1);
        expect(global.fetch).toHaveBeenCalledWith(expect.stringMatching(/\/api\/providers$/), {
            headers: { 'Content-Type': 'application/json' },
        });
        expect(providers).toEqual(mockProviders);
    });

    it('should throw an error when fetch fails', async () => {
        // Arrange
        const errorMessage = 'Network error';
        global.fetch = vi.fn().mockRejectedValue(new Error(errorMessage));

        // Act & Assert
        await expect(fetchProviders()).rejects.toThrow(errorMessage);
        expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    it('should throw an error when parsing JSON fails', async () => {
        // Arrange
        global.fetch = vi.fn().mockResolvedValue({
            json: vi.fn().mockRejectedValue(new SyntaxError('Unexpected end of JSON input')),
        });

        // Act & Assert
        await expect(fetchProviders()).rejects.toThrow('Unexpected end of JSON input');
        expect(global.fetch).toHaveBeenCalledTimes(1);
    });
});
