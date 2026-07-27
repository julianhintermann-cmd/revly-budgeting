import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { BudgetPage } from '@/pages/BudgetPage'
import { useAuthStore } from '@/stores/auth'
import type { User } from '@/lib/types'

vi.mock('@/hooks/queries', () => ({
  useBudget: () => ({
    data: {
      month: '2026-07',
      to_budget: 70000,
      income: 100000,
      assigned_total: 30000,
      activity_total: -12050,
      available_total: 12950,
      overspent_count: 1,
      categories: [
        {
          category_id: 1,
          name: 'Lebensmittel',
          icon: '🛒',
          color: '#10b981',
          parent_id: null,
          archived: false,
          rollover: true,
          assigned: 30000,
          activity: -12050,
          available: 17950,
        },
        {
          category_id: 2,
          name: 'Freizeit',
          icon: '🎉',
          color: '#8b5cf6',
          parent_id: null,
          archived: false,
          rollover: false,
          assigned: 0,
          activity: -5000,
          available: -5000,
        },
      ],
    },
    isLoading: false,
  }),
  useAutofill: () => ({ data: undefined }),
  useApplyAutofill: () => ({ mutate: vi.fn(), isPending: false }),
  useMoveBudget: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useAssignBudget: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateCategory: () => ({ mutate: vi.fn() }),
  useHouseholds: () => ({
    data: [{ id: 1, name: 'Haushalt', currency: 'CHF', role: 'owner', member_count: 1 }],
  }),
}))

describe('BudgetPage', () => {
  it('renders category rows with assigned, activity and available amounts', () => {
    useAuthStore.setState({
      user: { id: 1, active_household_id: 1, locale: 'de' } as User,
      status: 'authed',
    })
    render(<BudgetPage />)

    expect(screen.getByText('Lebensmittel')).toBeInTheDocument()
    expect(screen.getByText('Freizeit')).toBeInTheDocument()

    // assigned value is editable inline
    const assignInput = screen.getByLabelText('assign-1') as HTMLInputElement
    expect(assignInput.value).toBe('300.00')

    // "to budget" headline shows the remaining amount
    expect(screen.getAllByText(/700/).length).toBeGreaterThan(0)

    // overspent category surfaces the move-money hint
    expect(screen.getByText(/Überzogen|Overspent/i)).toBeInTheDocument()
  })
})
