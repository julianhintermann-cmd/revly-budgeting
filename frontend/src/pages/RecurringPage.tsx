import { Pencil, Play } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { CategorySelect } from '@/components/CategorySelect'
import { EmptyState } from '@/components/EmptyState'
import { Modal } from '@/components/Modal'
import { Money } from '@/components/Money'
import { Spinner } from '@/components/Spinner'
import {
  useAccounts,
  useCategories,
  useCreateRecurring,
  useDeleteRecurring,
  useRecurring,
  useRunRecurring,
  useUpdateRecurring,
} from '@/hooks/queries'
import { centsToInput, fmtDate, parseAmountInput, todayISO } from '@/lib/format'
import type { Frequency, Recurring } from '@/lib/types'

const FREQUENCIES: Frequency[] = ['weekly', 'monthly', 'quarterly', 'yearly', 'custom']

export function RecurringPage() {
  const { t } = useTranslation()
  const { data, isLoading } = useRecurring()
  const { data: accounts } = useAccounts()
  const { data: categories } = useCategories()
  const createRec = useCreateRecurring()
  const updateRec = useUpdateRecurring()
  const deleteRec = useDeleteRecurring()
  const runRec = useRunRecurring()

  const accMap = useMemo(() => new Map((accounts ?? []).map((a) => [a.id, a])), [accounts])

  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<Recurring | null>(null)
  const [kind, setKind] = useState<'expense' | 'income'>('expense')
  const [accountId, setAccountId] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [payee, setPayee] = useState('')
  const [amountText, setAmountText] = useState('')
  const [frequency, setFrequency] = useState<Frequency>('monthly')
  const [interval, setIntervalValue] = useState('1')
  const [nextDate, setNextDate] = useState(todayISO())
  const [endDate, setEndDate] = useState('')
  const [autoCreate, setAutoCreate] = useState(true)
  const [reminderDays, setReminderDays] = useState('3')
  const [notes, setNotes] = useState('')
  const [active, setActive] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const openForm = (rec: Recurring | null) => {
    setEditing(rec)
    setKind(rec ? (rec.amount >= 0 ? 'income' : 'expense') : 'expense')
    setAccountId(rec ? String(rec.account_id) : '')
    setCategoryId(rec?.category_id ? String(rec.category_id) : '')
    setPayee(rec?.payee ?? '')
    setAmountText(rec ? centsToInput(rec.amount) : '')
    setFrequency(rec?.frequency ?? 'monthly')
    setIntervalValue(String(rec?.interval ?? 1))
    setNextDate(rec?.next_date ?? todayISO())
    setEndDate(rec?.end_date ?? '')
    setAutoCreate(rec?.auto_create ?? true)
    setReminderDays(String(rec?.reminder_days ?? 3))
    setNotes(rec?.notes ?? '')
    setActive(rec?.active ?? true)
    setError(null)
    setFormOpen(true)
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    const cents = parseAmountInput(amountText)
    if (cents === null || cents <= 0 || !accountId) {
      setError(t('common.required'))
      return
    }
    const body = {
      account_id: Number(accountId),
      payee,
      amount: kind === 'income' ? cents : -cents,
      frequency,
      interval: Math.max(1, Number(interval) || 1),
      next_date: nextDate,
      auto_create: autoCreate,
      reminder_days: Math.max(0, Number(reminderDays) || 0),
      notes,
      ...(categoryId ? { category_id: Number(categoryId) } : editing ? { clear_category: true } : {}),
      ...(endDate ? { end_date: endDate } : editing ? { clear_end_date: true } : {}),
      ...(editing ? { active } : {}),
    }
    try {
      if (editing) await updateRec.mutateAsync({ id: editing.id, ...body })
      else await createRec.mutateAsync(body)
      setFormOpen(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    }
  }

  const remove = async () => {
    if (!editing || !window.confirm(t('common.confirm_delete'))) return
    await deleteRec.mutateAsync(editing.id)
    setFormOpen(false)
  }

  if (isLoading) return <Spinner />

  const items = data?.items ?? []
  const activeCount = items.filter((r) => r.active).length

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-bold">{t('recurring.title')}</h1>
        <div className="flex-1" />
        <button className="btn-primary" onClick={() => openForm(null)}>
          {t('recurring.new')}
        </button>
      </div>

      <div className="card flex flex-wrap items-center gap-6 p-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            {t('recurring.monthly_total')}
          </p>
          <p className="text-2xl font-bold">
            <Money cents={-(data?.monthly_expense_total ?? 0)} colored />
          </p>
        </div>
        <p className="text-sm text-slate-500">{t('recurring.subscriptions', { count: activeCount })}</p>
      </div>

      <div className="card overflow-x-auto">
        {items.length === 0 ? (
          <EmptyState text={t('common.no_data')} />
        ) : (
          <table className="w-full min-w-[640px] text-left">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-400 dark:border-slate-800">
                <th className="px-3 py-2">{t('transactions.payee')}</th>
                <th className="px-3 py-2">{t('common.account')}</th>
                <th className="px-3 py-2">{t('recurring.frequency')}</th>
                <th className="px-3 py-2">{t('recurring.next_date')}</th>
                <th className="px-3 py-2 text-right">{t('common.amount')}</th>
                <th className="px-3 py-2 text-right">{t('common.per_month')}</th>
                <th className="px-3 py-2 text-right">{t('common.actions')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
              {items.map((rec) => (
                <tr key={rec.id} className={rec.active ? '' : 'opacity-50'}>
                  <td className="px-3 py-2">
                    <p className="text-sm font-medium">{rec.payee || '—'}</p>
                    <p className="text-xs text-slate-400">
                      {rec.auto_create ? '🤖 ' + t('recurring.auto_create') : '🔔 ' + t('recurring.auto_create_hint')}
                      {!rec.active && ` · ${t('common.inactive')}`}
                    </p>
                  </td>
                  <td className="px-3 py-2 text-sm text-slate-500">{accMap.get(rec.account_id)?.name ?? '—'}</td>
                  <td className="px-3 py-2 text-sm">
                    {t(`recurring.freqs.${rec.frequency}`)}
                    {rec.interval > 1 && ` (${t('recurring.every', { count: rec.interval })})`}
                  </td>
                  <td className="px-3 py-2 text-sm text-slate-500">{fmtDate(rec.next_date)}</td>
                  <td className="px-3 py-2 text-right">
                    <Money
                      cents={rec.amount}
                      currency={accMap.get(rec.account_id)?.currency ?? 'CHF'}
                      colored
                      className="text-sm font-semibold"
                    />
                  </td>
                  <td className="px-3 py-2 text-right text-sm text-slate-500">
                    <Money cents={rec.monthly_equivalent} currency={accMap.get(rec.account_id)?.currency ?? 'CHF'} />
                  </td>
                  <td className="px-3 py-2 text-right">
                    <button
                      className="btn-ghost"
                      title={t('recurring.run_now')}
                      disabled={runRec.isPending}
                      onClick={() => runRec.mutate(rec.id)}
                    >
                      <Play className="h-4 w-4" />
                    </button>
                    <button className="btn-ghost" onClick={() => openForm(rec)}>
                      <Pencil className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editing ? t('recurring.edit') : t('recurring.new')}
        wide
      >
        <form onSubmit={submit} className="space-y-4">
          <div className="flex gap-1 rounded-lg bg-slate-100 p-1 dark:bg-slate-800">
            {(['expense', 'income'] as const).map((k) => (
              <button
                key={k}
                type="button"
                className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium ${
                  kind === k ? 'bg-white shadow-sm dark:bg-slate-700' : 'text-slate-500'
                }`}
                onClick={() => setKind(k)}
              >
                {t(`transactions.${k}`)}
              </button>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div>
              <label className="label">{t('common.account')}</label>
              <select className="input" value={accountId} onChange={(e) => setAccountId(e.target.value)} required>
                <option value="">–</option>
                {(accounts ?? [])
                  .filter((a) => !a.archived)
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
              </select>
            </div>
            <div>
              <label className="label">{t('transactions.payee')}</label>
              <input className="input" value={payee} onChange={(e) => setPayee(e.target.value)} />
            </div>
            <div>
              <label className="label">{t('common.amount')}</label>
              <input
                className="input"
                inputMode="decimal"
                placeholder="0.00"
                value={amountText}
                onChange={(e) => setAmountText(e.target.value)}
              />
            </div>
            <div>
              <label className="label">{t('common.category')}</label>
              <CategorySelect
                categories={categories ?? []}
                value={categoryId}
                onChange={setCategoryId}
                typeFilter={kind === 'income' ? 'income' : 'expense'}
              />
            </div>
            <div>
              <label className="label">{t('recurring.frequency')}</label>
              <select className="input" value={frequency} onChange={(e) => setFrequency(e.target.value as Frequency)}>
                {FREQUENCIES.map((f) => (
                  <option key={f} value={f}>
                    {t(`recurring.freqs.${f}`)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">{t('recurring.every', { count: Number(interval) || 1 })}</label>
              <input
                type="number"
                min={1}
                className="input"
                value={interval}
                onChange={(e) => setIntervalValue(e.target.value)}
              />
            </div>
            <div>
              <label className="label">{t('recurring.next_date')}</label>
              <input type="date" className="input" value={nextDate} onChange={(e) => setNextDate(e.target.value)} />
            </div>
            <div>
              <label className="label">
                {t('recurring.end_date')} ({t('common.optional')})
              </label>
              <input type="date" className="input" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
            </div>
            <div>
              <label className="label">{t('recurring.reminder_days')}</label>
              <input
                type="number"
                min={0}
                className="input"
                value={reminderDays}
                onChange={(e) => setReminderDays(e.target.value)}
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-6">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={autoCreate} onChange={(e) => setAutoCreate(e.target.checked)} />
              {t('recurring.auto_create')}
            </label>
            {editing && (
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
                {t('common.active')}
              </label>
            )}
          </div>
          <div>
            <label className="label">{t('common.notes')}</label>
            <input className="input" value={notes} onChange={(e) => setNotes(e.target.value)} />
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
              <button className="btn-primary" disabled={createRec.isPending || updateRec.isPending}>
                {t('common.save')}
              </button>
            </div>
          </div>
        </form>
      </Modal>
    </div>
  )
}
