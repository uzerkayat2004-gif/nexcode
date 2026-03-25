import { createConversation } from '../../lib/api';

describe('createConversation', () => {
    let originalFetch: typeof global.fetch;

    beforeEach(() => {
        originalFetch = global.fetch;
        global.fetch = jest.fn();
    });

    afterEach(() => {
        global.fetch = originalFetch;
    });

    it('creates a conversation with the default title', async () => {
        const mockResponse = { id: 'conv-123', title: 'New Chat' };
        (global.fetch as jest.Mock).mockResolvedValueOnce({
            json: jest.fn().mockResolvedValueOnce(mockResponse),
        });

        const result = await createConversation();

        expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/api/conversations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: 'New Chat' }),
        });
        expect(result).toEqual(mockResponse);
    });

    it('creates a conversation with a specific title', async () => {
        const mockResponse = { id: 'conv-456', title: 'My Custom Chat' };
        (global.fetch as jest.Mock).mockResolvedValueOnce({
            json: jest.fn().mockResolvedValueOnce(mockResponse),
        });

        const result = await createConversation('My Custom Chat');

        expect(global.fetch).toHaveBeenCalledWith('http://localhost:8000/api/conversations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: 'My Custom Chat' }),
        });
        expect(result).toEqual(mockResponse);
    });
});
