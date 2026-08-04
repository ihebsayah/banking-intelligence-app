import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';

const { mockGetHistory, mockSubmitQuery } = vi.hoisted(() => ({
  mockGetHistory: vi.fn(),
  mockSubmitQuery: vi.fn(),
}));

vi.mock('../../api/queryApi', () => ({
  queryApi: {
    getHistory: mockGetHistory,
    submitQuery: mockSubmitQuery,
  },
  SUGGESTED_QUERIES: [
    { category: 'Customer', label: 'Top customers by balance', query: 'top customers by balance' },
    { category: 'Customer', label: 'New customers 30 days', query: 'new customers 30 days' },
    { category: 'Risk', label: 'High-risk customers', query: 'risk score above 0.8' },
  ],
}));

import { Assistant } from '../Assistant';

function renderAssistant() {
  return render(
    <MemoryRouter>
      <Assistant />
    </MemoryRouter>
  );
}

const sampleResult = {
  query_id: 'q1',
  query_text: 'top customers',
  user_id: 'u',
  results: [
    { customer: 'Alice', balance: 1500 },
    { customer: 'Bob', balance: 900 },
  ],
  row_count: 2,
  execution_time_ms: 320,
  source: 'database',
  data_freshness: 'real-time',
  created_at: '2026-01-01T00:00:00Z',
  insights: undefined,
};

describe('Assistant', () => {
  beforeAll(() => {
    Element.prototype.scrollIntoView = vi.fn();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    mockGetHistory.mockResolvedValue([]);
    mockSubmitQuery.mockResolvedValue(sampleResult);
  });

  it('renders the welcome state', () => {
    renderAssistant();
    expect(screen.getByRole('heading', { name: 'AI Banking Assistant' })).toBeInTheDocument();
    expect(screen.getByText(/Banking Intelligence Assistant\. Ask me anything/)).toBeInTheDocument();
  });

  it('renders suggested query chips grouped by category', () => {
    renderAssistant();
    const categories = screen.getByRole('group', { name: 'Suggested query categories' });
    expect(categories).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Customer' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Risk' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Top customers by balance/ })).toBeInTheDocument();
    expect(categories.className).toContain('flex-wrap');
  });

  it('renders user and assistant messages in the transcript', async () => {
    renderAssistant();
    const input = screen.getByLabelText(/Ask a question about your banking data/);
    fireEvent.change(input, { target: { value: 'top customers by balance' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(() => {
      expect(screen.getByText('top customers by balance')).toBeInTheDocument();
    });
    expect(await screen.findByText(/Query complete — 2 records returned in 320ms/)).toBeInTheDocument();
  });

  it('shows the input and send button', () => {
    renderAssistant();
    expect(screen.getByLabelText(/Ask a question about your banking data/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Send message' })).toBeInTheDocument();
  });

  it('renders a loading state while a query is pending', async () => {
    let resolveQuery: (v: unknown) => void = () => {};
    mockSubmitQuery.mockReturnValue(new Promise((r) => { resolveQuery = r; }));
    renderAssistant();

    fireEvent.change(screen.getByLabelText(/Ask a question about your banking data/), { target: { value: 'any query' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));

    const status = screen.getByRole('status');
    expect(status).toBeInTheDocument();
    expect(status).toHaveAccessibleName('Assistant is typing');

    resolveQuery(sampleResult);
    await screen.findByText(/Query complete/);
  });

  it('toggles the history panel', async () => {
    renderAssistant();
    fireEvent.click(screen.getByRole('button', { name: 'History' }));
    expect(screen.getByLabelText('Query history')).toBeInTheDocument();
    expect(screen.getByText(/No queries yet/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Close history' }));
    expect(screen.queryByLabelText('Query history')).not.toBeInTheDocument();
  });

  it('renders result tabs after a query completes', async () => {
    renderAssistant();
    fireEvent.change(screen.getByLabelText(/Ask a question about your banking data/), { target: { value: 'top customers' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));
    await screen.findByText(/Query complete/);

    const tablist = screen.getByRole('tablist', { name: 'Result view' });
    expect(tablist).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Table/ })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Chart/ })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Raw/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('tab', { name: /Raw/ }));
    expect(screen.getByText(/Alice/)).toBeInTheDocument();
  });

  it('renders the result table container with scrollable wrapper', async () => {
    renderAssistant();
    fireEvent.change(screen.getByLabelText(/Ask a question about your banking data/), { target: { value: 'top customers' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));
    await screen.findByText(/Query complete/);

    const table = screen.getByRole('table');
    expect(table).toBeInTheDocument();
    expect(table.parentElement!.className).toContain('overflow-x-auto');
  });

  it('renders an error message when the query fails', async () => {
    mockSubmitQuery.mockRejectedValue(Object.assign(new Error('boom'), { response: { data: { detail: 'boom' } } }));
    renderAssistant();
    fireEvent.change(screen.getByLabelText(/Ask a question about your banking data/), { target: { value: 'bad query' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));
    expect(await screen.findByText(/Error executing query: boom/)).toBeInTheDocument();
  });

  it('renders a clarification message when backend returns requires_clarification', async () => {
    mockSubmitQuery.mockResolvedValue({
      ...sampleResult,
      requires_clarification: true,
      clarification: {
        requires_clarification: true,
        clarification_type: 'branch_resolution',
        message: "Branch 'Sfax Main Branch' was not found in the branch directory",
        candidates: [],
        raw_value: 'Sfax Main Branch',
      },
      results: [],
      row_count: 0,
    });
    renderAssistant();
    fireEvent.change(screen.getByLabelText(/Ask a question about your banking data/), { target: { value: 'clients at Sfax Main Branch' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send message' }));
    expect(await screen.findByText(/Sfax Main Branch.*was not found/)).toBeInTheDocument();
    expect(screen.queryByText(/Query complete/)).not.toBeInTheDocument();
  });

  it('uses flex column and internal scroll for the chat workspace', () => {
    const { container } = renderAssistant();
    const chat = container.querySelector('[data-testid="chat-messages"]')!;
    expect(chat.className).toContain('flex-1');
    expect(chat.className).toContain('overflow-y-auto');
    const inputWrap = container.querySelector('[data-testid="chat-input"]')!;
    expect(inputWrap.className).toContain('border-t');
    expect(inputWrap.className).toContain('flex-shrink-0');
  });
});
