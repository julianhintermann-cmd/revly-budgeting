export type Locale = 'de' | 'en'
export type Role = 'owner' | 'editor' | 'viewer'
export type AccountType = 'checking' | 'savings' | 'credit_card' | 'cash' | 'loan' | 'investment'
export type CategoryType = 'income' | 'expense'
export type TxnStatus = 'pending' | 'cleared' | 'reconciled'
export type Frequency = 'weekly' | 'monthly' | 'quarterly' | 'yearly' | 'custom'
export type DebtMethod = 'snowball' | 'avalanche'

export interface User {
  id: number
  email: string
  name: string
  locale: Locale
  is_admin: boolean
  totp_enabled: boolean
  email_notifications: boolean
  active_household_id: number | null
  created_at: string
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
  user: User
}

export interface TwoFARequired {
  requires_2fa: boolean
  temp_token: string
}

export interface Household {
  id: number
  name: string
  currency: string
  role: Role
  member_count: number
}

export interface Member {
  id: number
  user_id: number
  name: string
  email: string
  role: Role
}

export interface Invite {
  id: number
  code: string
  role: Role
  expires_at: string
  used: boolean
}

export interface Account {
  id: number
  name: string
  type: AccountType
  currency: string
  initial_balance: number
  note: string
  archived: boolean
  opening_date: string
  created_at: string
  balance: number
  cleared_balance: number
  balance_base: number
}

export interface Category {
  id: number
  name: string
  icon: string
  color: string
  type: CategoryType
  parent_id: number | null
  rollover: boolean
  archived: boolean
  sort_order: number
}

export interface Tag {
  id: number
  name: string
}

export interface Split {
  id: number
  category_id: number | null
  amount: number
  note: string
}

export interface Transaction {
  id: number
  account_id: number
  date: string
  amount: number
  payee: string
  notes: string
  category_id: number | null
  status: TxnStatus
  transfer_account_id: number | null
  transfer_group: string | null
  is_split: boolean
  splits: Split[]
  tags: string[]
  has_receipt: boolean
  recurring_id: number | null
  created_at: string
}

export interface TransactionList {
  items: Transaction[]
  total: number
  page: number
  page_size: number
  sum_amount: number
}

export interface TxnFilters {
  q?: string
  account_id?: number
  category_id?: number
  tag?: string
  status?: TxnStatus
  type?: 'in' | 'out'
  date_from?: string
  date_to?: string
  min_amount?: number
  max_amount?: number
  uncategorized?: boolean
  page?: number
  page_size?: number
}

export interface BudgetRow {
  category_id: number
  name: string
  icon: string
  color: string
  parent_id: number | null
  archived: boolean
  rollover: boolean
  assigned: number
  activity: number
  available: number
}

export interface BudgetMonth {
  month: string
  to_budget: number
  income: number
  assigned_total: number
  activity_total: number
  available_total: number
  overspent_count: number
  categories: BudgetRow[]
}

export interface AutofillSuggestion {
  category_id: number
  suggested: number
}

export interface Recurring {
  id: number
  account_id: number
  category_id: number | null
  payee: string
  amount: number
  frequency: Frequency
  interval: number
  next_date: string
  end_date: string | null
  auto_create: boolean
  reminder_days: number
  active: boolean
  notes: string
  last_run_date: string | null
  monthly_equivalent: number
  created_at: string
}

export interface RecurringList {
  items: Recurring[]
  monthly_expense_total: number
}

export interface Upcoming {
  id: number
  payee: string
  amount: number
  next_date: string
  days_until: number
  account_id: number
  category_id: number | null
  auto_create: boolean
}

export interface Goal {
  id: number
  name: string
  icon: string
  target_amount: number
  current_amount: number
  target_date: string | null
  account_id: number | null
  notes: string
  progress_pct: number
  monthly_needed: number | null
  completed_at: string | null
  created_at: string
}

export interface Debt {
  id: number
  name: string
  account_id: number | null
  balance: number
  apr_bps: number
  min_payment: number
}

export interface PlanSettings {
  method: DebtMethod
  monthly_budget: number
}

export interface PlanMonthRow {
  index: number
  month: string
  total_paid: number
  interest: number
  remaining: number
  balances: Record<string, number>
}

export interface DebtPlan {
  method: DebtMethod
  monthly_budget: number
  months_to_free: number
  total_interest: number
  debt_free_month: string | null
  truncated: boolean
  warning: string | null
  schedule: PlanMonthRow[]
  summaries: Record<string, { months: number; total_interest: number }>
}

export interface SpendingRow {
  category_id: number | null
  name: string
  icon: string
  color: string
  amount: number
}

export interface Spending {
  start: string
  end: string
  total: number
  rows: SpendingRow[]
}

export interface TrendRow {
  month: string
  income: number
  expenses: number
  net: number
}

export interface CalendarDay {
  day: string
  inflow: number
  outflow: number
  net: number
  balance: number
}

export interface CashflowCalendar {
  month: string
  start_balance: number
  days: CalendarDay[]
  tight_days: number
}

export interface NetWorthRow {
  month: string
  assets: number
  liabilities: number
  net: number
}

export interface FlowRow {
  name: string
  icon: string
  color: string
  amount: number
}

export interface MoneyFlow {
  month: string
  income: FlowRow[]
  expenses: FlowRow[]
  income_total: number
  expense_total: number
}

export interface AppNotification {
  id: number
  type: string
  title: string
  body: string
  data: Record<string, unknown> | null
  read: boolean
  created_at: string
}

export interface NotificationList {
  items: AppNotification[]
  unread_count: number
}

export interface ImportPreview {
  cache_id: string
  format: 'csv' | 'ofx' | 'qif'
  columns: string[]
  rows: Record<string, string>[]
  row_count: number
}

export interface ImportResult {
  imported: number
  duplicates_skipped: number
  errors: number
}

export interface ApiToken {
  id: number
  name: string
  prefix: string
  last_used_at: string | null
  expires_at: string | null
  created_at: string
}

export interface ApiTokenCreated extends ApiToken {
  token: string
}

export interface SmtpSettings {
  host: string
  port: number
  username: string
  from_email: string
  use_tls: boolean
  has_password: boolean
  configured: boolean
}

export interface RateItem {
  currency: string
  rate: number
}

export interface Rates {
  base_currency: string
  rates: RateItem[]
}
