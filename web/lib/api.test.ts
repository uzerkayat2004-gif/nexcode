import { deleteConversation } from './api';

// Mock the global fetch
const originalFetch = global.fetch;

beforeEach(() => {
    global.fetch = jest.fn();
});

afterEach(() => {
    global.fetch = originalFetch;
});

describe('deleteConversation', () => {
    it('should call fetch with correct URL and DELETE method', async () => {
        const mockId = '123';
        const mockResponse = { success: true };

        // Setup mock response
        (global.fetch as jest.Mock).mockResolvedValueOnce({
            json: jest.fn().mockResolvedValueOnce(mockResponse)
        });

        const result = await deleteConversation(mockId);

        expect(global.fetch).toHaveBeenCalledWith(
            `http://localhost:8000/api/conversations/${mockId}`,
            expect.objectContaining({
                method: 'DELETE',
            })
        );
        expect(result).toEqual(mockResponse);
    });
});
