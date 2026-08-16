import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import React from 'react';

const { mockSearchCustomers } = vi.hoisted(() => ({
  mockSearchCustomers: vi.fn(),
}));

vi.mock('../../../api/customer360Api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../../api/customer360Api')>();
  return {
    ...actual,
    customer360Api: {
      ...actual.customer360Api,
      searchCustomers: mockSearchCustomers,
    },
  };
});

import { CustomerSearchPage } from '../CustomerSearchPage';

describe('CustomerSearchPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderComponent = () =>
    render(
      <MemoryRouter initialEntries={['/workbench/customers']}>
        <Routes>
          <Route path="/workbench/customers" element={<CustomerSearchPage />} />
          <Route
            path="/workbench/customers/:customerId"
            element={<div data-testid="customer-360-detail-target">Customer 360 Detail Page</div>}
          />
        </Routes>
      </MemoryRouter>,
    );

  it('renders search input and prompt state on initial load', () => {
    renderComponent();
    expect(screen.getByText('Customer 360')).toBeInTheDocument();
    expect(
      screen.getByText('Search for an authorized customer to open their consolidated profile.'),
    ).toBeInTheDocument();
    expect(screen.getByTestId('customer-search-input')).toBeInTheDocument();
    expect(screen.getByText('Find a Customer')).toBeInTheDocument();
    expect(mockSearchCustomers).not.toHaveBeenCalled();
  });

  it('does not call search API when query is empty or less than 2 characters', async () => {
    renderComponent();
    const input = screen.getByTestId('customer-search-input');

    fireEvent.change(input, { target: { value: 'a' } });

    await waitFor(() => {
      expect(
        screen.getByText('Please enter at least 2 characters to search.'),
      ).toBeInTheDocument();
    });

    expect(mockSearchCustomers).not.toHaveBeenCalled();
  });

  it('calls search API and renders minimal customer item when query is valid', async () => {
    mockSearchCustomers.mockResolvedValueOnce({
      items: [
        {
          customer_id: 'CUST_00001',
          name: 'Fouad Ben Salah',
          segment: 'PART_PREM',
        },
      ],
      total: 1,
      limit: 20,
      offset: 0,
    });

    renderComponent();
    const input = screen.getByTestId('customer-search-input');

    fireEvent.change(input, { target: { value: 'Fouad' } });

    await waitFor(() => {
      expect(mockSearchCustomers).toHaveBeenCalledWith({ q: 'Fouad', limit: 20, offset: 0 });
    });

    expect(await screen.findByText('Fouad Ben Salah')).toBeInTheDocument();
    expect(screen.getByText('ID: CUST_00001')).toBeInTheDocument();
    expect(screen.getByText('PART_PREM')).toBeInTheDocument();
    expect(screen.getByTestId('open-customer-360-CUST_00001')).toBeInTheDocument();
  });

  it('navigates to /workbench/customers/:customerId upon selecting result', async () => {
    mockSearchCustomers.mockResolvedValueOnce({
      items: [
        {
          customer_id: 'CUST_00001',
          name: 'Fouad Ben Salah',
          segment: 'PART_PREM',
        },
      ],
      total: 1,
      limit: 20,
      offset: 0,
    });

    renderComponent();
    const input = screen.getByTestId('customer-search-input');

    fireEvent.change(input, { target: { value: 'CUST_00001' } });

    const openBtn = await screen.findByTestId('open-customer-360-CUST_00001');
    fireEvent.click(openBtn);

    expect(await screen.findByTestId('customer-360-detail-target')).toBeInTheDocument();
  });

  it('displays no-results state when API returns empty items', async () => {
    mockSearchCustomers.mockResolvedValueOnce({
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
    });

    renderComponent();
    const input = screen.getByTestId('customer-search-input');

    fireEvent.change(input, { target: { value: 'UNKNOWN_USER' } });

    expect(await screen.findByText('No matching customers found')).toBeInTheDocument();
  });

  it('displays error state on API failure', async () => {
    mockSearchCustomers.mockRejectedValueOnce({
      response: { status: 503, data: { detail: { message: 'Data source offline' } } },
    });

    renderComponent();
    const input = screen.getByTestId('customer-search-input');

    fireEvent.change(input, { target: { value: 'ERROR_TEST' } });

    expect(await screen.findByText(/The customer data source is temporarily unavailable/)).toBeInTheDocument();
  });
});
