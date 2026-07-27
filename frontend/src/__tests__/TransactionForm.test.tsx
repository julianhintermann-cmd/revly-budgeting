import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { TransactionFormModal } from '@/components/TransactionForm'
import { useUiStore } from '@/stores/ui'

const { createMock } = vi.hoisted(() => ({ createMock: vi.fn().mockResolvedValue({}) }))

vi.mock('@/hooks/queries', () => ({
  useAccounts: () => ({
    data: [
      {
        id: 1,
        name: 'Giro',
        type: 'checking',
        currency: 'CHF',
        initial_balance: 0,
        note: '',
        archived: false,
        opening_date: '2026-01-01',
        created_at: '2026-01-01T00:00:00Z',
        balance: 0,
        cleared_balance: 0,
        balance_base: 0,
      },
    ],
  }),
  useCategories: () => ({
    data: [
      {
        id: 5,
        name: 'Lebensmittel',
        icon: '🛒',
        color: '#10b981',
        type: 'expense',
        parent_id: null,
        rollover: true,
        archived: false,
        sort_order: 0,
      },
    ],
  }),
  useCreateTransaction: () => ({ mutateAsync: createMock, isPending: false }),
  useUpdateTransaction: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUploadReceipt: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

describe('TransactionFormModal', () => {
  beforeEach(() => {
    createMock.mockClear()
    useUiStore.setState({ txnModal: { open: true, txn: null } })
  })

  it('validates required fields before submitting', async () => {
    render(<TransactionFormModal />)
    fireEvent.click(screen.getByText('Speichern'))
    await waitFor(() => {
      expect(screen.getAllByText('Pflichtfeld').length).toBeGreaterThan(0)
    })
    expect(createMock).not.toHaveBeenCalled()
  })

  it('submits an expense with a negative signed amount', async () => {
    render(<TransactionFormModal />)

    const selects = screen.getAllByRole('combobox')
    fireEvent.change(selects[0], { target: { value: '1' } }) // account
    fireEvent.change(screen.getByPlaceholderText('0.00'), { target: { value: '12.50' } })

    fireEvent.click(screen.getByText('Speichern'))

    await waitFor(() => expect(createMock).toHaveBeenCalledTimes(1))
    const payload = createMock.mock.calls[0][0]
    expect(payload.amount).toBe(-1250)
    expect(payload.account_id).toBe(1)
  })

  it('rejects splits that do not add up', async () => {
    render(<TransactionFormModal />)

    const selects = screen.getAllByRole('combobox')
    fireEvent.change(selects[0], { target: { value: '1' } })
    fireEvent.change(screen.getByPlaceholderText('0.00'), { target: { value: '50.00' } })

    fireEvent.click(screen.getByLabelText('Aufteilen'))
    const amountInputs = screen.getAllByPlaceholderText('0.00')
    // index 0 is the total; 1 & 2 are the split rows
    fireEvent.change(amountInputs[1], { target: { value: '30.00' } })
    fireEvent.change(amountInputs[2], { target: { value: '10.00' } })

    fireEvent.click(screen.getByText('Speichern'))
    await waitFor(() => {
      expect(screen.getByText(/Restbetrag/)).toBeInTheDocument()
    })
    expect(createMock).not.toHaveBeenCalled()
  })
})
