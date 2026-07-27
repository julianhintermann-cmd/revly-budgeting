import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '@/lib/api'
import type {
  Account,
  ApiToken,
  ApiTokenCreated,
  AutofillSuggestion,
  BudgetMonth,
  CashflowCalendar,
  Category,
  Debt,
  DebtPlan,
  Goal,
  Household,
  ImportPreview,
  ImportResult,
  Invite,
  Member,
  MoneyFlow,
  NetWorthRow,
  NotificationList,
  PlanSettings,
  Rates,
  Recurring,
  RecurringList,
  SmtpSettings,
  Spending,
  Tag,
  Transaction,
  TransactionList,
  TrendRow,
  TxnFilters,
  Upcoming,
  User,
} from '@/lib/types'
import { useAuthStore } from '@/stores/auth'

function useInvalidator() {
  const qc = useQueryClient()
  return (keys: string[][]) => {
    for (const key of keys) void qc.invalidateQueries({ queryKey: key })
  }
}

const TXN_RELATED: string[][] = [
  ['transactions'],
  ['accounts'],
  ['budget'],
  ['reports'],
  ['notifications'],
  ['goals'],
  ['debts'],
  ['recurring'],
]

// ---------- user / profile ----------

export function useUpdateMe() {
  const setUser = useAuthStore((s) => s.setUser)
  return useMutation({
    mutationFn: (body: Partial<Pick<User, 'name' | 'locale' | 'email_notifications'>>) =>
      api<User>('/users/me', { method: 'PATCH', body }),
    onSuccess: (user) => setUser(user),
  })
}

export async function refreshMe(): Promise<User> {
  const user = await api<User>('/users/me')
  useAuthStore.getState().setUser(user)
  return user
}

// ---------- households ----------

export function useHouseholds() {
  return useQuery({ queryKey: ['households'], queryFn: () => api<Household[]>('/households') })
}

export function useCreateHousehold() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { name: string; currency: string }) =>
      api<Household>('/households', { method: 'POST', body }),
    onSuccess: async () => {
      await refreshMe()
      qc.clear()
    },
  })
}

export function useSwitchHousehold() {
  const qc = useQueryClient()
  const setUser = useAuthStore((s) => s.setUser)
  return useMutation({
    mutationFn: (household_id: number) =>
      api<User>('/users/me/active-household', { method: 'POST', body: { household_id } }),
    onSuccess: (user) => {
      setUser(user)
      qc.clear()
    },
  })
}

export function useJoinHousehold() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (code: string) => api<Household>('/households/join', { method: 'POST', body: { code } }),
    onSuccess: async () => {
      await refreshMe()
      qc.clear()
    },
  })
}

export function useMembers(householdId: number | null) {
  return useQuery({
    queryKey: ['members', householdId],
    queryFn: () => api<Member[]>(`/households/${householdId}/members`),
    enabled: householdId != null,
  })
}

export function useChangeMemberRole(householdId: number | null) {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: string }) =>
      api<void>(`/households/${householdId}/members/${userId}`, { method: 'PATCH', body: { role } }),
    onSuccess: () => invalidate([['members'], ['households']]),
  })
}

export function useRemoveMember(householdId: number | null) {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (userId: number) =>
      api<void>(`/households/${householdId}/members/${userId}`, { method: 'DELETE' }),
    onSuccess: () => invalidate([['members'], ['households']]),
  })
}

export function useInvites(householdId: number | null, enabled: boolean) {
  return useQuery({
    queryKey: ['invites', householdId],
    queryFn: () => api<Invite[]>(`/households/${householdId}/invites`),
    enabled: householdId != null && enabled,
  })
}

export function useCreateInvite(householdId: number | null) {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (role: string) =>
      api<Invite>(`/households/${householdId}/invites`, { method: 'POST', body: { role } }),
    onSuccess: () => invalidate([['invites']]),
  })
}

export function useDeleteInvite(householdId: number | null) {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (inviteId: number) =>
      api<void>(`/households/${householdId}/invites/${inviteId}`, { method: 'DELETE' }),
    onSuccess: () => invalidate([['invites']]),
  })
}

// ---------- accounts / rates ----------

export function useAccounts() {
  return useQuery({ queryKey: ['accounts'], queryFn: () => api<Account[]>('/accounts') })
}

export function useCreateAccount() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api<Account>('/accounts', { method: 'POST', body }),
    onSuccess: () => invalidate([['accounts'], ['budget'], ['reports']]),
  })
}

export function useUpdateAccount() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number } & Record<string, unknown>) =>
      api<Account>(`/accounts/${id}`, { method: 'PATCH', body }),
    onSuccess: () => invalidate([['accounts'], ['budget'], ['reports']]),
  })
}

export function useDeleteAccount() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (id: number) => api<void>(`/accounts/${id}`, { method: 'DELETE' }),
    onSuccess: () => invalidate([['accounts'], ['budget'], ['reports']]),
  })
}

export function useReconcile() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: ({ id, statement_balance }: { id: number; statement_balance: number }) =>
      api<{ difference: number; adjustment_transaction_id: number | null; reconciled_count: number }>(
        `/accounts/${id}/reconcile`,
        { method: 'POST', body: { statement_balance } }
      ),
    onSuccess: () => invalidate(TXN_RELATED),
  })
}

export function useRates() {
  return useQuery({ queryKey: ['rates'], queryFn: () => api<Rates>('/exchange-rates') })
}

export function useSaveRates() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (rates: { currency: string; rate: number }[]) =>
      api<Rates>('/exchange-rates', { method: 'PUT', body: { rates } }),
    onSuccess: () => invalidate([['rates'], ['accounts'], ['budget'], ['reports']]),
  })
}

// ---------- categories / tags ----------

export function useCategories() {
  return useQuery({ queryKey: ['categories'], queryFn: () => api<Category[]>('/categories') })
}

export function useCreateCategory() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api<Category>('/categories', { method: 'POST', body }),
    onSuccess: () => invalidate([['categories'], ['budget']]),
  })
}

export function useUpdateCategory() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number } & Record<string, unknown>) =>
      api<Category>(`/categories/${id}`, { method: 'PATCH', body }),
    onSuccess: () => invalidate([['categories'], ['budget'], ['reports']]),
  })
}

export function useDeleteCategory() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (id: number) => api<void>(`/categories/${id}`, { method: 'DELETE' }),
    onSuccess: () => invalidate([['categories'], ['budget']]),
  })
}

export function useTags() {
  return useQuery({ queryKey: ['tags'], queryFn: () => api<Tag[]>('/tags') })
}

// ---------- transactions ----------

export function useTransactions(filters: TxnFilters) {
  return useQuery({
    queryKey: ['transactions', filters],
    queryFn: () => api<TransactionList>('/transactions', { params: filters as Record<string, unknown> }),
  })
}

export function useCreateTransaction() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<Transaction>('/transactions', { method: 'POST', body }),
    onSuccess: () => invalidate(TXN_RELATED),
  })
}

export function useUpdateTransaction() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number } & Record<string, unknown>) =>
      api<Transaction>(`/transactions/${id}`, { method: 'PATCH', body }),
    onSuccess: () => invalidate(TXN_RELATED),
  })
}

export function useDeleteTransaction() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (id: number) => api<void>(`/transactions/${id}`, { method: 'DELETE' }),
    onSuccess: () => invalidate(TXN_RELATED),
  })
}

export function useBulkAction() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<{ affected: number; skipped: number }>('/transactions/bulk', { method: 'POST', body }),
    onSuccess: () => invalidate(TXN_RELATED),
  })
}

export function useUploadReceipt() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: ({ id, file }: { id: number; file: File }) => {
      const formData = new FormData()
      formData.append('file', file)
      return api<Transaction>(`/transactions/${id}/receipt`, { method: 'POST', formData })
    },
    onSuccess: () => invalidate([['transactions']]),
  })
}

// ---------- budget ----------

export function useBudget(month: string) {
  return useQuery({
    queryKey: ['budget', month],
    queryFn: () => api<BudgetMonth>('/budgets', { params: { month } }),
  })
}

export function useAssignBudget() {
  const invalidate = useInvalidator()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { month: string; category_id: number; assigned: number }) =>
      api<BudgetMonth>('/budgets', { method: 'PUT', body }),
    onSuccess: (data) => {
      qc.setQueryData(['budget', data.month], data)
      invalidate([['budget'], ['reports']])
    },
  })
}

export function useMoveBudget() {
  const invalidate = useInvalidator()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      month: string
      from_category_id: number | null
      to_category_id: number | null
      amount: number
    }) => api<BudgetMonth>('/budgets/move', { method: 'POST', body }),
    onSuccess: (data) => {
      qc.setQueryData(['budget', data.month], data)
      invalidate([['budget']])
    },
  })
}

export function useAutofill(month: string, enabled: boolean) {
  return useQuery({
    queryKey: ['budget', 'autofill', month],
    queryFn: () =>
      api<{ month: string; suggestions: AutofillSuggestion[] }>('/budgets/autofill', {
        params: { month },
      }),
    enabled,
  })
}

export function useApplyAutofill() {
  const invalidate = useInvalidator()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (month: string) =>
      api<BudgetMonth>('/budgets/autofill/apply', { method: 'POST', body: { month } }),
    onSuccess: (data) => {
      qc.setQueryData(['budget', data.month], data)
      invalidate([['budget']])
    },
  })
}

// ---------- recurring ----------

export function useRecurring() {
  return useQuery({ queryKey: ['recurring'], queryFn: () => api<RecurringList>('/recurring') })
}

export function useUpcoming(days = 30) {
  return useQuery({
    queryKey: ['recurring', 'upcoming', days],
    queryFn: () => api<Upcoming[]>('/recurring/upcoming', { params: { days } }),
  })
}

export function useCreateRecurring() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api<Recurring>('/recurring', { method: 'POST', body }),
    onSuccess: () => invalidate([['recurring']]),
  })
}

export function useUpdateRecurring() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number } & Record<string, unknown>) =>
      api<Recurring>(`/recurring/${id}`, { method: 'PATCH', body }),
    onSuccess: () => invalidate([['recurring']]),
  })
}

export function useDeleteRecurring() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (id: number) => api<void>(`/recurring/${id}`, { method: 'DELETE' }),
    onSuccess: () => invalidate([['recurring']]),
  })
}

export function useRunRecurring() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (id: number) => api<{ transaction_id: number }>(`/recurring/${id}/run`, { method: 'POST' }),
    onSuccess: () => invalidate(TXN_RELATED),
  })
}

// ---------- goals ----------

export function useGoals() {
  return useQuery({ queryKey: ['goals'], queryFn: () => api<Goal[]>('/goals') })
}

export function useCreateGoal() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api<Goal>('/goals', { method: 'POST', body }),
    onSuccess: () => invalidate([['goals']]),
  })
}

export function useUpdateGoal() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number } & Record<string, unknown>) =>
      api<Goal>(`/goals/${id}`, { method: 'PATCH', body }),
    onSuccess: () => invalidate([['goals']]),
  })
}

export function useDeleteGoal() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (id: number) => api<void>(`/goals/${id}`, { method: 'DELETE' }),
    onSuccess: () => invalidate([['goals']]),
  })
}

export function useContribute() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: ({ id, amount }: { id: number; amount: number }) =>
      api<Goal>(`/goals/${id}/contribute`, { method: 'POST', body: { amount } }),
    onSuccess: () => invalidate([['goals'], ['notifications']]),
  })
}

// ---------- debts ----------

export function useDebts() {
  return useQuery({ queryKey: ['debts'], queryFn: () => api<Debt[]>('/debts') })
}

export function useCreateDebt() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api<Debt>('/debts', { method: 'POST', body }),
    onSuccess: () => invalidate([['debts']]),
  })
}

export function useUpdateDebt() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: ({ id, ...body }: { id: number } & Record<string, unknown>) =>
      api<Debt>(`/debts/${id}`, { method: 'PATCH', body }),
    onSuccess: () => invalidate([['debts']]),
  })
}

export function useDeleteDebt() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (id: number) => api<void>(`/debts/${id}`, { method: 'DELETE' }),
    onSuccess: () => invalidate([['debts']]),
  })
}

export function usePlanSettings() {
  return useQuery({
    queryKey: ['debts', 'plan-settings'],
    queryFn: () => api<PlanSettings>('/debts/plan-settings'),
  })
}

export function useSavePlanSettings() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (body: PlanSettings) => api<PlanSettings>('/debts/plan-settings', { method: 'PUT', body }),
    onSuccess: () => invalidate([['debts']]),
  })
}

export function useDebtPlan(params: { method?: string; monthly_budget?: number }) {
  return useQuery({
    queryKey: ['debts', 'plan', params],
    queryFn: () => api<DebtPlan>('/debts/plan', { params }),
  })
}

// ---------- reports ----------

export function useSpending(dateFrom?: string, dateTo?: string) {
  return useQuery({
    queryKey: ['reports', 'spending', dateFrom, dateTo],
    queryFn: () =>
      api<Spending>('/reports/spending', { params: { date_from: dateFrom, date_to: dateTo } }),
  })
}

export function useTrend(months = 12) {
  return useQuery({
    queryKey: ['reports', 'trend', months],
    queryFn: () => api<TrendRow[]>('/reports/trend', { params: { months } }),
  })
}

export function useNetWorth(months = 24) {
  return useQuery({
    queryKey: ['reports', 'net-worth', months],
    queryFn: () => api<NetWorthRow[]>('/reports/net-worth', { params: { months } }),
  })
}

export function useMoneyFlow(month: string) {
  return useQuery({
    queryKey: ['reports', 'money-flow', month],
    queryFn: () => api<MoneyFlow>('/reports/money-flow', { params: { month } }),
  })
}

export function useCashflowCalendar(month: string) {
  return useQuery({
    queryKey: ['reports', 'calendar', month],
    queryFn: () => api<CashflowCalendar>('/reports/cashflow-calendar', { params: { month } }),
  })
}

// ---------- notifications ----------

export function useNotifications() {
  return useQuery({
    queryKey: ['notifications'],
    queryFn: () => api<NotificationList>('/notifications'),
    refetchInterval: 60_000,
  })
}

export function useMarkRead() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (body: { ids?: number[]; all?: boolean }) =>
      api<{ updated: number }>('/notifications/read', { method: 'POST', body }),
    onSuccess: () => invalidate([['notifications']]),
  })
}

// ---------- api tokens ----------

export function useApiTokens() {
  return useQuery({ queryKey: ['api-tokens'], queryFn: () => api<ApiToken[]>('/users/me/tokens') })
}

export function useCreateApiToken() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (body: { name: string; expires_days?: number }) =>
      api<ApiTokenCreated>('/users/me/tokens', { method: 'POST', body }),
    onSuccess: () => invalidate([['api-tokens']]),
  })
}

export function useDeleteApiToken() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (id: number) => api<void>(`/users/me/tokens/${id}`, { method: 'DELETE' }),
    onSuccess: () => invalidate([['api-tokens']]),
  })
}

// ---------- admin ----------

export function useSmtp(enabled: boolean) {
  return useQuery({
    queryKey: ['smtp'],
    queryFn: () => api<SmtpSettings>('/admin/smtp'),
    enabled,
  })
}

export function useSaveSmtp() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api<SmtpSettings>('/admin/smtp', { method: 'PUT', body }),
    onSuccess: () => invalidate([['smtp']]),
  })
}

export function useTestSmtp() {
  return useMutation({
    mutationFn: (to?: string) =>
      api<{ sent: boolean; to: string }>('/admin/smtp/test', { method: 'POST', body: { to } }),
  })
}

// ---------- import ----------

export function useImportPreview() {
  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      return api<ImportPreview>('/import/preview', { method: 'POST', formData })
    },
  })
}

export function useImportCommit() {
  const invalidate = useInvalidator()
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api<ImportResult>('/import/commit', { method: 'POST', body }),
    onSuccess: () => invalidate(TXN_RELATED),
  })
}
