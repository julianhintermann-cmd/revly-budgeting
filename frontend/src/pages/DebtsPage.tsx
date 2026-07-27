import { Pencil } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import { ChartTooltip } from '@/components/ChartTooltip'
import { EmptyState } from '@/components/EmptyState'
import { Modal } from '@/components/Modal'
import { Money } from '@/components/Money'
import { Spinner } from '@/components/Spinner'
import {
  useAccounts,
  useCreateDebt,
  useDebtPlan,
  useDebts,
  useDeleteDebt,
  usePlanSettings,
  useSavePlanSettings,
  useUpdateDebt,
} from '@/hooks/queries'
import { useChartTheme } from '@/lib/chartTheme'
import { centsToInput, fmtMonth, fmtMonthShort, parseAmountInput } from '@/lib/format'
import type { Debt, DebtMethod } from '@/lib/types'

export function DebtsPage() {
  const { t } = useTranslation()
  const chart = useChartTheme()
  const { data: debts, isLoading } = useDebts()
  const { data: settings } = usePlanSettings()
  const saveSettings = useSavePlanSettings()
  const { data: plan } = useDebtPlan({})
  const createDebt = useCreateDebt()
  const updateDebt = useUpdateDebt()
  const deleteDebt = useDeleteDebt()
  const { data: accounts } = useAccounts()

  const [budgetText, setBudgetText] = useState<string | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<Debt | null>(null)
  const [name, setName] = useState('')
  const [balanceText, setBalanceText] = useState('')
  const [aprText, setAprText] = useState('')
  const [minText, setMinText] = useState('')
  const [accountId, setAccountId] = useState('')
  const [error, setError] = useState<string | null>(null)

  const openForm = (debt: Debt | null) => {
    setEditing(debt)
    setName(debt?.name ?? '')
    setBalanceText(debt ? centsToInput(debt.balance) : '')
    setAprText(debt ? String(debt.apr_bps / 100) : '')
    setMinText(debt ? centsToInput(debt.min_payment) : '')
    setAccountId(debt?.account_id ? String(debt.account_id) : '')
    setError(null)
    setFormOpen(true)
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    const balance = balanceText.trim() ? parseAmountInput(balanceText) : 0
    const minPayment = minText.trim() ? parseAmountInput(minText) : 0
    const apr = aprText.trim() ? Number(aprText.replace(',', '.')) : 0
    if (balance === null || minPayment === null || Number.isNaN(apr)) {
      setError(t('common.required'))
      return
    }
    const body = {
      name,
      balance,
      min_payment: minPayment,
      apr_bps: Math.round(apr * 100),
      ...(accountId ? { account_id: Number(accountId) } : editing ? { clear_account: true } : {}),
    }
    try {
      if (editing) await updateDebt.mutateAsync({ id: editing.id, ...body })
      else await createDebt.mutateAsync(body)
      setFormOpen(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    }
  }

  const remove = async () => {
    if (!editing || !window.confirm(t('common.confirm_delete'))) return
    await deleteDebt.mutateAsync(editing.id)
    setFormOpen(false)
  }

  const commitBudget = () => {
    if (budgetText === null || !settings) return
    const cents = budgetText.trim() ? parseAmountInput(budgetText) : 0
    if (cents !== null && cents >= 0) {
      saveSettings.mutate({ method: settings.method, monthly_budget: cents })
    }
    setBudgetText(null)
  }

  const setMethod = (method: DebtMethod) => {
    if (settings) saveSettings.mutate({ method, monthly_budget: settings.monthly_budget })
  }

  if (isLoading) return <Spinner />

  const chartData = plan?.schedule.map((row) => ({ month: row.month, remaining: row.remaining })) ?? []

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-bold">{t('debts.title')}</h1>
        <div className="flex-1" />
        <button className="btn-primary" onClick={() => openForm(null)}>
          {t('debts.new')}
        </button>
      </div>

      {(debts?.length ?? 0) === 0 ? (
        <div className="card">
          <EmptyState text={t('debts.no_debts')} />
        </div>
      ) : (
        <>
          <div className="card overflow-x-auto">
            <table className="w-full min-w-[480px] text-left">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-400 dark:border-slate-800">
                  <th className="px-3 py-2">{t('common.name')}</th>
                  <th className="px-3 py-2 text-right">{t('debts.balance')}</th>
                  <th className="px-3 py-2 text-right">{t('debts.apr')}</th>
                  <th className="px-3 py-2 text-right">{t('debts.min_payment')}</th>
                  <th className="w-10 px-2 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                {debts?.map((debt) => (
                  <tr key={debt.id}>
                    <td className="px-3 py-2">
                      <p className="text-sm font-medium">{debt.name}</p>
                      {debt.account_id && (
                        <p className="text-xs text-slate-400">
                          {accounts?.find((a) => a.id === debt.account_id)?.name}
                        </p>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Money cents={debt.balance} className="text-sm font-semibold" />
                    </td>
                    <td className="px-3 py-2 text-right text-sm text-slate-500">
                      {(debt.apr_bps / 100).toFixed(2)} %
                    </td>
                    <td className="px-3 py-2 text-right text-sm text-slate-500">
                      <Money cents={debt.min_payment} />
                    </td>
                    <td className="px-2 py-2 text-right">
                      <button className="btn-ghost" onClick={() => openForm(debt)}>
                        <Pencil className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card space-y-4 p-4">
            <div className="flex flex-wrap items-end gap-4">
              <div>
                <label className="label">{t('debts.method')}</label>
                <div className="flex gap-1 rounded-lg bg-slate-100 p-1 dark:bg-slate-800">
                  {(['snowball', 'avalanche'] as const).map((m) => (
                    <button
                      key={m}
                      className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                        settings?.method === m ? 'bg-white shadow-sm dark:bg-slate-700' : 'text-slate-500'
                      }`}
                      onClick={() => setMethod(m)}
                      title={t(`debts.${m}_hint`)}
                    >
                      {t(`debts.${m}`)}
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="label">{t('debts.monthly_budget')}</label>
                <input
                  className="input w-40"
                  inputMode="decimal"
                  value={budgetText ?? centsToInput(settings?.monthly_budget ?? 0)}
                  onFocus={(e) => {
                    setBudgetText(centsToInput(settings?.monthly_budget ?? 0))
                    e.target.select()
                  }}
                  onChange={(e) => setBudgetText(e.target.value)}
                  onBlur={commitBudget}
                  onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
                />
              </div>
              {plan && plan.months_to_free > 0 && (
                <div className="flex gap-6 text-sm">
                  <div>
                    <p className="text-xs text-slate-400">{t('debts.months_to_free')}</p>
                    <p className="text-lg font-bold">{plan.months_to_free}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400">{t('debts.total_interest')}</p>
                    <p className="text-lg font-bold">
                      <Money cents={plan.total_interest} />
                    </p>
                  </div>
                  {plan.debt_free_month && (
                    <div>
                      <p className="text-xs text-slate-400">{t('debts.plan')}</p>
                      <p className="text-lg font-bold capitalize">
                        {t('debts.debt_free', { month: fmtMonth(plan.debt_free_month) })}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </div>

            {plan?.warning === 'budget_below_minimums' && (
              <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-700 dark:bg-amber-950/40 dark:text-amber-400">
                ⚠️ {t('debts.warning_min')}
              </p>
            )}
            {plan?.warning === 'not_payable' || plan?.warning === 'no_budget' ? (
              <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950/40 dark:text-red-400">
                {t('debts.warning_not_payable')}
              </p>
            ) : null}

            {plan && (
              <div className="grid gap-2 text-sm sm:grid-cols-2">
                {(['snowball', 'avalanche'] as const).map((m) => (
                  <div
                    key={m}
                    className={`rounded-lg border p-3 ${
                      settings?.method === m
                        ? 'border-emerald-300 dark:border-emerald-800'
                        : 'border-slate-200 dark:border-slate-800'
                    }`}
                  >
                    <p className="font-medium">{t(`debts.${m}`)}</p>
                    <p className="text-xs text-slate-500">{t(`debts.${m}_hint`)}</p>
                    <p className="mt-1 text-xs">
                      {plan.summaries[m]?.months ?? 0} {t('common.month')} ·{' '}
                      {t('debts.total_interest')}:{' '}
                      <Money cents={plan.summaries[m]?.total_interest ?? 0} />
                    </p>
                  </div>
                ))}
              </div>
            )}

            {chartData.length > 1 && (
              <div>
                <h3 className="mb-1 text-sm font-semibold">
                  {t('debts.remaining')} – {t('debts.plan')}
                </h3>
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                      <defs>
                        <linearGradient id="debtRemaining" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor={chart.expense} stopOpacity={0.25} />
                          <stop offset="100%" stopColor={chart.expense} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid stroke={chart.grid} vertical={false} />
                      <XAxis
                        dataKey="month"
                        tickFormatter={(m) => fmtMonthShort(String(m))}
                        tick={{ fill: chart.axisText, fontSize: 11 }}
                        tickLine={false}
                        axisLine={false}
                        minTickGap={24}
                      />
                      <YAxis
                        tickFormatter={(v) => `${Math.round(Number(v) / 100000) / 10}k`}
                        tick={{ fill: chart.axisText, fontSize: 11 }}
                        tickLine={false}
                        axisLine={false}
                        width={44}
                      />
                      <Tooltip
                        content={<ChartTooltip labelFormatter={(l) => fmtMonth(String(l))} />}
                      />
                      <Area
                        type="monotone"
                        dataKey="remaining"
                        name={t('debts.remaining')}
                        stroke={chart.expense}
                        strokeWidth={2}
                        fill="url(#debtRemaining)"
                        dot={false}
                        activeDot={{ r: 4 }}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </div>
        </>
      )}

      <Modal open={formOpen} onClose={() => setFormOpen(false)} title={editing ? t('debts.edit') : t('debts.new')}>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label">{t('common.name')}</label>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="label">{t('debts.balance')}</label>
              <input
                className="input"
                inputMode="decimal"
                placeholder="0.00"
                value={balanceText}
                onChange={(e) => setBalanceText(e.target.value)}
                disabled={Boolean(accountId)}
              />
            </div>
            <div>
              <label className="label">{t('debts.apr')}</label>
              <input
                className="input"
                inputMode="decimal"
                placeholder="12.5"
                value={aprText}
                onChange={(e) => setAprText(e.target.value)}
              />
            </div>
            <div>
              <label className="label">{t('debts.min_payment')}</label>
              <input
                className="input"
                inputMode="decimal"
                placeholder="0.00"
                value={minText}
                onChange={(e) => setMinText(e.target.value)}
              />
            </div>
          </div>
          <div>
            <label className="label">
              {t('debts.linked_account')} ({t('common.optional')})
            </label>
            <select className="input" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
              <option value="">{t('common.none')}</option>
              {(accounts ?? [])
                .filter((a) => a.type === 'credit_card' || a.type === 'loan')
                .map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
            </select>
          </div>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex justify-between">
            {editing ? (
              <button type="button" className="btn-danger" onClick={remove}>
                {t('common.delete')}
              </button>
            ) : (
              <span />
            )}
            <div className="flex gap-2">
              <button type="button" className="btn-secondary" onClick={() => setFormOpen(false)}>
                {t('common.cancel')}
              </button>
              <button className="btn-primary" disabled={createDebt.isPending || updateDebt.isPending}>
                {t('common.save')}
              </button>
            </div>
          </div>
        </form>
      </Modal>
    </div>
  )
}
