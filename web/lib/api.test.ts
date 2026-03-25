import { fetchConversations, Conversation } from './api';

// Mock the global fetch function
global.fetch = jest.fn() as jest.Mock;

describe('fetchConversations', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should fetch conversations successfully', async () => {
    const mockConversations: Conversation[] = [
      { id: '1', title: 'Chat 1', created_at: '2023-01-01', updated_at: '2023-01-01', message_count: 5 },
      { id: '2', title: 'Chat 2', created_at: '2023-01-02', updated_at: '2023-01-02', message_count: 10 },
    ];

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: jest.fn().mockResolvedValueOnce(mockConversations),
    });

    const result = await fetchConversations();

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/conversations'),
        expect.objectContaining({ headers: { "Content-Type": "application/json" } })
    );
    expect(result).toEqual(mockConversations);
  });

  it('should handle fetch errors', async () => {
    const errorMessage = 'Network Error';
    (global.fetch as jest.Mock).mockRejectedValueOnce(new Error(errorMessage));

    await expect(fetchConversations()).rejects.toThrow(errorMessage);

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/conversations'),
        expect.objectContaining({ headers: { "Content-Type": "application/json" } })
    );
  });
});
