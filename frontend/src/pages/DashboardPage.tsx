import { ArrowRight, Sparkles } from 'lucide-react'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { Area, AreaChart, ResponsiveContainer, Tooltip } from 'recharts'

import { ChartTooltip } from '@/components/ChartTooltip'
import { Money } from '@/components/Money'
import { ProgressBar } from '@/components/ProgressBar'
import { Spinner } from '@/components/Spinner'
import {
  useAccounts,
  useBudget,
  useCategories,
  useHouseholds,
  useNetWorth,
  useTransactions,
  useUpcoming,
} from '@/hooks/queries'
import { useChartTheme } from '@/lib/chartTheme'
import { currentMonth, fmtDate, fmtMonth, fmtMonthShort } from '@/lib/format'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

export function DashboardPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const chart = useChartTheme()
  const user = useAuthStore((s) => s.user)
  const openTxnModal = useUiStore((s) => s.openTxnModal)
  const month = currentMonth()

  const { data: accounts, isLoading } = useAccounts()
  const { data: budget } = useBudget(month)
  const { data: netWorth } = useNetWorth(12)
  const { data: upcoming } = useUpcoming(14)
  const { data: recent } = useTransactions({ page_size: 8 })
  const { data: categories } = useCategories()
  const { data: households } = useHouseholds()

  const currency = households?.find((h) => h.id === user?.active_household_id)?.currency ?? 'CHF'
  const catMap = useMemo(() => new Map((categories ?? []).map((c) => [c.id, c])), [categories])
  const accMap = useMemo(() => new Map((accounts ?? []).map((a) => [a.id, a])), [accounts])

  const activeAccounts = (accounts ?? []).filter((a) => !a.archived)
  const totalNet = activeAccounts.reduce((sum, a) => sum + a.balance_base, 0)
  const spent = -(budget?.activity_total ?? 0)
  const assigned = budget?.assigned_total ?? 0

  if (isLoading) return <Spinner />

  if (activeAccounts.length === 0) {
    return (
      <div className="card mx-auto max-w-lg p-8 text-center">
        <Sparkles className="mx-auto mb-3 h-8 w-8 text-emerald-500" />
        <h1 className="mb-1 text-xl font-bold">{t('onboarding.title')}</h1>
        <p className="mb-4 text-sm text-slate-500 dark:text-slate-400">{t('onboarding.subtitle')}</p>
        <Link to="/onboarding" className="btn-primary">
          {t('onboarding.step1_title')} <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">{t('dashboard.title')}</h1>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="card p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{t('dashboard.net_worth')}</p>
          <p className="mt-1 text-2xl font-bold">
            <Money cents={totalNet} currency={currency} />
          </p>
          {netWorth && netWorth.length > 1 && (
            <div className="mt-2 h-14">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={netWorth} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
                  <defs>
                    <linearGradient id="nw" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={chart.net} stopOpacity={0.25} />
                      <stop offset="100%" stopColor={chart.net} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <Tooltip
                    content={
                      <ChartTooltip currency={currency} labelFormatter={(l) => fmtMonthShort(String(l))} />
                    }
                  />
                  <Area
                    type="monotone"
                    dataKey="net"
                    name={t('reports.net')}
                    stroke={chart.net}
                    strokeWidth={2}
                    fill="url(#nw)"
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        <div className="card p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{t('dashboard.to_budget')}</p>
          <p
            className={`mt-1 text-2xl font-bold ${
              (budget?.to_budget ?? 0) < 0 ? 'text-red-600 dark:text-red-400' : 'text-emerald-600 dark:text-emerald-400'
            }`}
          >
            <Money cents={budget?.to_budget ?? 0} currency={currency} />
          </p>
          <Link
            to="/budget"
            className="mt-2 inline-flex items-center gap-1 text-sm text-emerald-600 hover:underline dark:text-emerald-400"
          >
            {t('nav.budget')} <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>

        <div className="card p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            {t('dashboard.budget_progress', { month: fmtMonth(month) })}
          </p>
          <p className="mt-1 text-sm">
            {t('dashboard.spent_of', {
              spent: new Intl.NumberFormat().format(Math.round(spent / 100)),
              assigned: new Intl.NumberFormat().format(Math.round(assigned / 100)),
            })}
          </p>
          <ProgressBar
            className="mt-2"
            value={assigned > 0 ? (spent / assigned) * 100 : 0}
            danger={spent > assigned}
          />
          {(budget?.overspent_count ?? 0) > 0 && (
            <p className="mt-2 text-xs text-red-600 dark:text-red-400">
              ⚠️ {t('dashboard.overspent', { count: budget?.overspent_count })}
            </p>
          )}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="card p-4">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold">{t('dashboard.accounts')}</h2>
            <Link to="/accounts" className="text-xs text-emerald-600 hover:underline dark:text-emerald-400">
              {t('dashboard.view_all')}
            </Link>
          </div>
          <ul className="divide-y divide-slate-100 dark:divide-slate-800">
            {activeAccounts.slice(0, 6).map((a) => (
              <li key={a.id} className="flex items-center justify-between py-2 text-sm">
                <span className="truncate">{a.name}</span>
                <Money cents={a.balance} currency={a.currency} colored className="font-medium" />
              </li>
            ))}
          </ul>
        </div>

        <div className="card p-4">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold">{t('dashboard.upcoming')}</h2>
            <Link to="/recurring" className="text-xs text-emerald-600 hover:underline dark:text-emerald-400">
              {t('dashboard.view_all')}
            </Link>
          </div>
          {(upcoming?.length ?? 0) === 0 ? (
            <p className="py-4 text-center text-sm text-slate-400">{t('dashboard.no_bills')}</p>
          ) : (
            <ul className="divide-y divide-slate-100 dark:divide-slate-800">
              {upcoming?.slice(0, 6).map((u) => (
                <li key={`${u.id}-${u.next_date}`} className="flex items-center justify-between py-2 text-sm">
                  <div className="min-w-0">
                    <p className="truncate">{u.payee || '—'}</p>
                    <p className="text-xs text-slate-400">
                      {u.days_until === 0
                        ? t('dashboard.due_today')
                        : t('dashboard.due_in', { count: u.days_until })}
                    </p>
                  </div>
                  <Money
                    cents={u.amount}
                    currency={accMap.get(u.account_id)?.currency ?? currency}
                    colored
                    className="font-medium"
                  />
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="card p-4">
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-semibold">{t('dashboard.recent')}</h2>
            <Link to="/transactions" className="text-xs text-emerald-600 hover:underline dark:text-emerald-400">
              {t('dashboard.view_all')}
            </Link>
          </div>
          {(recent?.items.length ?? 0) === 0 ? (
            <button className="btn-secondary mx-auto my-4 block" onClick={() => openTxnModal()}>
              {t('dashboard.new_transaction')}
            </button>
          ) : (
            <ul className="divide-y divide-slate-100 dark:divide-slate-800">
              {recent?.items.map((txn) => {
                const cat = txn.category_id ? catMap.get(txn.category_id) : null
                return (
                  <li key={txn.id} className="flex items-center gap-2 py-2 text-sm">
                    <span className="text-base">{txn.transfer_group ? '🔁' : (cat?.icon ?? '❓')}</span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate">{txn.payee || cat?.name || '—'}</p>
                      <p className="text-xs text-slate-400">{fmtDate(txn.date)}</p>
                    </div>
                    <Money
                      cents={txn.amount}
                      currency={accMap.get(txn.account_id)?.currency ?? currency}
                      colored
                      className="font-medium"
                    />
                  </li>
                )
              })}
            </ul>
          )}
        </div>
      </div>

      <p className="text-center text-xs text-slate-400" onClick={() => navigate('/transactions')}>
        {t('dashboard.this_month')}: {t('dashboard.income')}{' '}
        <Money cents={budget?.income ?? 0} currency={currency} /> · {t('dashboard.expenses')}{' '}
        <Money cents={spent} currency={currency} />
      </p>
    </div>
  )
}
