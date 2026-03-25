import { renameConversation } from '../api';

describe('renameConversation', () => {
    beforeEach(() => {
        global.fetch = jest.fn() as jest.Mock;
    });

    afterEach(() => {
        jest.restoreAllMocks();
    });

    it('should rename a conversation with the correct arguments', async () => {
        const mockResponse = { id: '123', title: 'New Title' };
        (global.fetch as jest.Mock).mockResolvedValue({
            json: jest.fn().mockResolvedValue(mockResponse),
        });

        const result = await renameConversation('123', 'New Title');

        expect(global.fetch).toHaveBeenCalledWith(
            expect.stringContaining('/api/conversations/123'),
            expect.objectContaining({
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title: 'New Title' }),
            })
        );
        expect(result).toEqual(mockResponse);
    });
});
