import { Pencil, PiggyBank } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { EmptyState } from '@/components/EmptyState'
import { Modal } from '@/components/Modal'
import { Money } from '@/components/Money'
import { ProgressBar } from '@/components/ProgressBar'
import { Spinner } from '@/components/Spinner'
import {
  useAccounts,
  useContribute,
  useCreateGoal,
  useDeleteGoal,
  useGoals,
  useUpdateGoal,
} from '@/hooks/queries'
import { centsToInput, fmtDate, fmtMoney, parseAmountInput } from '@/lib/format'
import type { Goal } from '@/lib/types'

export function GoalsPage() {
  const { t } = useTranslation()
  const { data: goals, isLoading } = useGoals()
  const { data: accounts } = useAccounts()
  const createGoal = useCreateGoal()
  const updateGoal = useUpdateGoal()
  const deleteGoal = useDeleteGoal()
  const contribute = useContribute()

  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<Goal | null>(null)
  const [name, setName] = useState('')
  const [icon, setIcon] = useState('🎯')
  const [targetText, setTargetText] = useState('')
  const [currentText, setCurrentText] = useState('')
  const [targetDate, setTargetDate] = useState('')
  const [accountId, setAccountId] = useState('')
  const [error, setError] = useState<string | null>(null)

  const [contributeFor, setContributeFor] = useState<Goal | null>(null)
  const [contributeText, setContributeText] = useState('')

  const openForm = (goal: Goal | null) => {
    setEditing(goal)
    setName(goal?.name ?? '')
    setIcon(goal?.icon ?? '🎯')
    setTargetText(goal ? centsToInput(goal.target_amount) : '')
    setCurrentText(goal && !goal.account_id ? centsToInput(goal.current_amount) : '')
    setTargetDate(goal?.target_date ?? '')
    setAccountId(goal?.account_id ? String(goal.account_id) : '')
    setError(null)
    setFormOpen(true)
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    const target = parseAmountInput(targetText)
    if (target === null || target <= 0) {
      setError(t('common.required'))
      return
    }
    const current = currentText.trim() ? (parseAmountInput(currentText) ?? 0) : 0
    const body = {
      name,
      icon,
      target_amount: target,
      ...(accountId
        ? { account_id: Number(accountId) }
        : { current_amount: current, ...(editing ? { clear_account: true } : {}) }),
      ...(targetDate ? { target_date: targetDate } : editing ? { clear_target_date: true } : {}),
    }
    try {
      if (editing) await updateGoal.mutateAsync({ id: editing.id, ...body })
      else await createGoal.mutateAsync(body)
      setFormOpen(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    }
  }

  const remove = async () => {
    if (!editing || !window.confirm(t('common.confirm_delete'))) return
    await deleteGoal.mutateAsync(editing.id)
    setFormOpen(false)
  }

  const submitContribute = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!contributeFor) return
    const cents = parseAmountInput(contributeText)
    if (cents === null || cents === 0) return
    await contribute.mutateAsync({ id: contributeFor.id, amount: cents })
    setContributeFor(null)
    setContributeText('')
  }

  if (isLoading) return <Spinner />

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-bold">{t('goals.title')}</h1>
        <div className="flex-1" />
        <button className="btn-primary" onClick={() => openForm(null)}>
          {t('goals.new')}
        </button>
      </div>

      {(goals?.length ?? 0) === 0 ? (
        <div className="card">
          <EmptyState
            text={t('common.no_data')}
            action={
              <button className="btn-secondary" onClick={() => openForm(null)}>
                {t('goals.new')}
              </button>
            }
          />
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {goals?.map((goal) => {
            const reached = goal.progress_pct >= 100
            return (
              <div key={goal.id} className={`card p-4 ${reached ? 'border-emerald-300 dark:border-emerald-800' : ''}`}>
                <div className="flex items-start justify-between">
                  <span className="text-2xl">{goal.icon}</span>
                  <button className="btn-ghost" onClick={() => openForm(goal)}>
                    <Pencil className="h-4 w-4" />
                  </button>
                </div>
                <p className="mt-1 font-semibold">{goal.name}</p>
                <p className="text-sm text-slate-500">
                  <Money cents={goal.current_amount} /> / <Money cents={goal.target_amount} />
                </p>
                <ProgressBar className="mt-2" value={goal.progress_pct} />
                <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                  <span>{t('goals.progress', { pct: goal.progress_pct })}</span>
                  {goal.target_date && <span>{fmtDate(goal.target_date)}</span>}
                </div>
                {reached ? (
                  <p className="mt-2 text-sm font-medium text-emerald-600 dark:text-emerald-400">
                    {t('goals.reached')}
                  </p>
                ) : (
                  goal.monthly_needed !== null && (
                    <p className="mt-2 text-xs text-slate-500">
                      {t('goals.monthly_needed', { amount: fmtMoney(goal.monthly_needed) })}
                    </p>
                  )
                )}
                {goal.account_id ? (
                  <p className="mt-2 text-xs text-slate-400">
                    <PiggyBank className="mr-1 inline h-3.5 w-3.5" />
                    {accounts?.find((a) => a.id === goal.account_id)?.name}
                  </p>
                ) : (
                  <button
                    className="mt-2 text-xs text-emerald-600 hover:underline dark:text-emerald-400"
                    onClick={() => setContributeFor(goal)}
                  >
                    + {t('goals.contribute')}
                  </button>
                )}
              </div>
            )
          })}
        </div>
      )}

      <Modal open={formOpen} onClose={() => setFormOpen(false)} title={editing ? t('goals.edit') : t('goals.new')}>
        <form onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-4 gap-3">
            <div className="col-span-3">
              <label className="label">{t('common.name')}</label>
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div>
              <label className="label">{t('categories.icon')}</label>
              <input className="input text-center" maxLength={4} value={icon} onChange={(e) => setIcon(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">{t('goals.target_amount')}</label>
              <input
                className="input"
                inputMode="decimal"
                placeholder="0.00"
                value={targetText}
                onChange={(e) => setTargetText(e.target.value)}
              />
            </div>
            <div>
              <label className="label">
                {t('goals.target_date')} ({t('common.optional')})
              </label>
              <input type="date" className="input" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} />
            </div>
          </div>
          <div>
            <label className="label">
              {t('goals.linked_account')} ({t('common.optional')})
            </label>
            <select className="input" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
              <option value="">{t('common.none')}</option>
              {(accounts ?? [])
                .filter((a) => !a.archived)
                .map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
            </select>
            <p className="mt-1 text-xs text-slate-400">
              {accountId ? t('goals.linked_hint') : t('goals.manual_hint')}
            </p>
          </div>
          {!accountId && (
            <div>
              <label className="label">{t('goals.current')}</label>
              <input
                className="input"
                inputMode="decimal"
                placeholder="0.00"
                value={currentText}
                onChange={(e) => setCurrentText(e.target.value)}
              />
            </div>
          )}
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
              <button className="btn-primary" disabled={createGoal.isPending || updateGoal.isPending}>
                {t('common.save')}
              </button>
            </div>
          </div>
        </form>
      </Modal>

      <Modal
        open={contributeFor !== null}
        onClose={() => setContributeFor(null)}
        title={t('goals.contribute')}
      >
        <form onSubmit={submitContribute} className="space-y-4">
          <div>
            <label className="label">{t('common.amount')}</label>
            <input
              className="input"
              inputMode="decimal"
              placeholder="0.00"
              value={contributeText}
              onChange={(e) => setContributeText(e.target.value)}
              autoFocus
            />
          </div>
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-secondary" onClick={() => setContributeFor(null)}>
              {t('common.cancel')}
            </button>
            <button className="btn-primary" disabled={contribute.isPending}>
              {t('common.save')}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
