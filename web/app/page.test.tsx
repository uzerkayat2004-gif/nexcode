import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Home from './page';
import * as api from '@/lib/api';
import userEvent from '@testing-library/user-event';

// Mock dependencies
vi.mock('@/lib/api', () => ({
  fetchProviders: vi.fn(),
  fetchSettings: vi.fn(),
  fetchConversations: vi.fn(),
  fetchAuthStatus: vi.fn(),
  sendStreamingMessage: vi.fn(),
  switchModel: vi.fn(),
  updateSettings: vi.fn(),
  setApiKey: vi.fn(),
  deleteApiKey: vi.fn(),
  deleteConversation: vi.fn(),
  startOAuth: vi.fn(),
}));

describe('Home Page', () => {
  const mockProviders = [
    { id: 'openrouter', name: 'OpenRouter', description: 'desc', models: ['model-1'] },
  ];
  const mockSettings = {
    max_tokens: 1000,
    theme: 'dark',
    permission_mode: 'ask',
    authenticated_providers: ['openrouter'],
    api_keys: { openrouter: 'sk-123' },
  };
  const mockConversations = [
    { id: 'conv-1', title: 'Test Chat', updated_at: '2023-01-01T00:00:00.000Z' },
  ];

  beforeEach(() => {
    vi.resetAllMocks();
    (api.fetchProviders as any).mockResolvedValue(mockProviders);
    (api.fetchSettings as any).mockResolvedValue(mockSettings);
    (api.fetchConversations as any).mockResolvedValue(mockConversations);
    (api.fetchAuthStatus as any).mockResolvedValue({});

    // Mock scrollIntoView
    window.HTMLElement.prototype.scrollIntoView = vi.fn();
  });

  it('renders correctly initially with sidebar closed and empty chat state', async () => {
    render(<Home />);

    // Check header (multiple 'NexCode' exist, so we use getAllByText or specific queries)
    expect(screen.getAllByText('NexCode').length).toBeGreaterThan(0);

    // Check empty state
    expect(screen.getByText('Welcome to NexCode')).toBeInTheDocument();
    expect(screen.getByText('Create a Python project')).toBeInTheDocument();

    // Check initial API calls
    await waitFor(() => {
      expect(api.fetchProviders).toHaveBeenCalledTimes(1);
      expect(api.fetchSettings).toHaveBeenCalledTimes(1);
      expect(api.fetchConversations).toHaveBeenCalledTimes(1);
      expect(api.fetchAuthStatus).toHaveBeenCalledTimes(1);
    });
  });

  it('can open and close the sidebar', async () => {
    render(<Home />);

    const sidebar = screen.getByRole('complementary'); // <aside> role
    expect(sidebar).not.toHaveClass('open');

    // Open sidebar
    const hamburgerBtn = screen.getByText('☰');
    await userEvent.click(hamburgerBtn);
    expect(sidebar).toHaveClass('open');

    // Close sidebar via overlay
    const overlay = document.querySelector('.sidebar-overlay') as HTMLElement;
    await userEvent.click(overlay);
    expect(sidebar).not.toHaveClass('open');
  });

  it('can open and close the settings modal', async () => {
    render(<Home />);

    // Settings modal is not present initially
    expect(screen.queryByText('⚙️ General')).not.toBeInTheDocument();

    // Open settings via sidebar footer
    const settingsBtn = screen.getByText('⚙️ Settings');
    await userEvent.click(settingsBtn);

    // Wait for settings to open (depends on fetchSettings resolving)
    await waitFor(() => {
      expect(screen.getByText('⚙️ General')).toBeInTheDocument();
    });

    // Close settings
    const closeBtn = document.querySelector('.modal-close') as HTMLElement;
    if (closeBtn) await userEvent.click(closeBtn);

    await waitFor(() => {
      expect(screen.queryByText('⚙️ General')).not.toBeInTheDocument();
    });
  });

  it('can create a new chat via sidebar button', async () => {
    render(<Home />);

    const newChatBtn = screen.getByText('+ New');
    await userEvent.click(newChatBtn);

    // The chat area should be reset to empty state (it already is empty initially, but we can verify it doesn't crash)
    expect(screen.getByText('Welcome to NexCode')).toBeInTheDocument();
  });

  it('can open the model selector modal', async () => {
    render(<Home />);

    // Click header model button
    const headerModelBtn = document.querySelector('.header-model-btn') as HTMLElement;
    await userEvent.click(headerModelBtn);

    await waitFor(() => {
      expect(screen.getByText('Select Model')).toBeInTheDocument();
    });

    // Close model selector
    const closeBtn = document.querySelector('.modal-close') as HTMLElement;
    if (closeBtn) await userEvent.click(closeBtn);

    await waitFor(() => {
      expect(screen.queryByText('Select Model')).not.toBeInTheDocument();
    });
  });

  it('can type and send a message', async () => {
    // Setup the mock for sendStreamingMessage to simulate a response
    (api.sendStreamingMessage as any).mockImplementation((text: string, sessionId: string | null, callbacks: any) => {
      callbacks.onSessionCreated('new-session-id');
      callbacks.onToken('Hello, ');
      callbacks.onToken('world!');
      callbacks.onDone('Hello, world!', 'new-session-id', 'test-model', 'test-provider');
    });

    render(<Home />);

    // Wait for the empty state to appear to ensure app is ready
    expect(screen.getByText('Welcome to NexCode')).toBeInTheDocument();

    const input = screen.getByPlaceholderText('Ask NexCode anything...');

    // Type a message
    await userEvent.type(input, 'Hello NexCode{enter}');

    // After enter, the message should appear
    await waitFor(() => {
      expect(screen.getByText('Hello NexCode')).toBeInTheDocument();
    });

    // Check that our simulated response appears
    await waitFor(() => {
      expect(screen.getByText('Hello, world!')).toBeInTheDocument();
    });

    // Verify the mock was called with the right text
    expect(api.sendStreamingMessage).toHaveBeenCalledWith(
      'Hello NexCode',
      null,
      expect.any(Object)
    );
  });
});
