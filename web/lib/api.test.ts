import { fetchModels } from './api';

describe('api', () => {
    let originalFetch: typeof global.fetch;

    beforeEach(() => {
        originalFetch = global.fetch;
        global.fetch = jest.fn() as jest.Mock;
    });

    afterEach(() => {
        global.fetch = originalFetch;
        jest.clearAllMocks();
    });

    describe('fetchModels', () => {
        it('should make a GET request to /api/models and return the parsed JSON response', async () => {
            const mockResponse = { models: ['model-a', 'model-b'] };
            (global.fetch as jest.Mock).mockResolvedValueOnce({
                ok: true,
                json: jest.fn().mockResolvedValueOnce(mockResponse),
            });

            const result = await fetchModels();

            expect(global.fetch).toHaveBeenCalledTimes(1);
            expect(global.fetch).toHaveBeenCalledWith(
                expect.stringContaining('/api/models'),
                expect.objectContaining({
                    headers: expect.anything()
                })
            );
            expect(result).toEqual(mockResponse);
        });

        it('should handle network errors correctly', async () => {
            (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

            await expect(fetchModels()).rejects.toThrow('Network error');
        });
    });
});
