import { ArrowLeftRight, RotateCcw, RotateCw, Wand2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Modal } from '@/components/Modal'
import { Money } from '@/components/Money'
import { MonthSwitcher } from '@/components/MonthSwitcher'
import { Spinner } from '@/components/Spinner'
import {
  useApplyAutofill,
  useAssignBudget,
  useAutofill,
  useBudget,
  useHouseholds,
  useMoveBudget,
  useUpdateCategory,
} from '@/hooks/queries'
import { centsToInput, currentMonth, fmtNumber, parseAmountInput } from '@/lib/format'
import type { BudgetRow } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'

function AssignCell({
  row,
  month,
  currency,
}: {
  row: BudgetRow
  month: string
  currency: string
}) {
  const [text, setText] = useState<string | null>(null)
  const assign = useAssignBudget()

  const commit = () => {
    if (text === null) return
    const cents = text.trim() === '' ? 0 : parseAmountInput(text)
    if (cents !== null && cents >= 0 && cents !== row.assigned) {
      assign.mutate({ month, category_id: row.category_id, assigned: cents })
    }
    setText(null)
  }

  return (
    <input
      className="input w-24 py-1 text-right text-sm sm:w-28"
      inputMode="decimal"
      aria-label={`assign-${row.category_id}`}
      value={text ?? centsToInput(row.assigned)}
      onFocus={(e) => {
        setText(centsToInput(row.assigned))
        e.target.select()
      }}
      onChange={(e) => setText(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
        if (e.key === 'Escape') setText(null)
      }}
      title={currency}
    />
  )
}

export function BudgetPage() {
  const { t } = useTranslation()
  const user = useAuthStore((s) => s.user)
  const [month, setMonth] = useState(currentMonth())
  const [showAutofill, setShowAutofill] = useState(false)
  const [moveOpen, setMoveOpen] = useState(false)
  const [moveFrom, setMoveFrom] = useState('')
  const [moveTo, setMoveTo] = useState('')
  const [moveAmountText, setMoveAmountText] = useState('')
  const [moveError, setMoveError] = useState<string | null>(null)

  const { data: budget, isLoading } = useBudget(month)
  const { data: autofill } = useAutofill(month, showAutofill)
  const applyAutofill = useApplyAutofill()
  const moveBudget = useMoveBudget()
  const updateCategory = useUpdateCategory()
  const { data: households } = useHouseholds()
  const currency = households?.find((h) => h.id === user?.active_household_id)?.currency ?? 'CHF'

  const rows = useMemo(() => {
    const all = budget?.categories ?? []
    return all.filter((r) => !r.archived || r.assigned !== 0 || r.activity !== 0 || r.available !== 0)
  }, [budget])

  const suggestionMap = useMemo(
    () => new Map((autofill?.suggestions ?? []).map((s) => [s.category_id, s.suggested])),
    [autofill]
  )

  const openMove = (toCategoryId?: number) => {
    setMoveFrom('')
    setMoveTo(toCategoryId ? String(toCategoryId) : '')
    setMoveAmountText('')
    setMoveError(null)
    setMoveOpen(true)
  }

  const submitMove = async (e: React.FormEvent) => {
    e.preventDefault()
    setMoveError(null)
    const cents = parseAmountInput(moveAmountText)
    if (cents === null || cents <= 0) {
      setMoveError(t('common.required'))
      return
    }
    try {
      await moveBudget.mutateAsync({
        month,
        from_category_id: moveFrom ? Number(moveFrom) : null,
        to_category_id: moveTo ? Number(moveTo) : null,
        amount: cents,
      })
      setMoveOpen(false)
    } catch (err) {
      setMoveError(err instanceof Error ? err.message : t('common.error'))
    }
  }

  if (isLoading || !budget) return <Spinner />

  const tbb = budget.to_budget

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-bold">{t('budget.title')}</h1>
        <MonthSwitcher month={month} onChange={setMonth} />
        <div className="flex-1" />
        <button className="btn-secondary" onClick={() => openMove()}>
          <ArrowLeftRight className="h-4 w-4" /> {t('budget.move')}
        </button>
        <button className="btn-secondary" onClick={() => setShowAutofill((v) => !v)}>
          <Wand2 className="h-4 w-4" /> {t('budget.autofill')}
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div
          className={`card p-4 ${
            tbb < 0
              ? 'border-red-300 dark:border-red-900'
              : tbb === 0
                ? 'border-emerald-300 dark:border-emerald-900'
                : ''
          }`}
        >
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{t('budget.to_budget')}</p>
          <p
            className={`mt-1 text-2xl font-bold ${
              tbb < 0
                ? 'text-red-600 dark:text-red-400'
                : 'text-emerald-600 dark:text-emerald-400'
            }`}
          >
            <Money cents={tbb} currency={currency} />
          </p>
          <p className="mt-1 text-xs text-slate-400">
            {tbb === 0 ? t('budget.all_assigned') : tbb < 0 ? t('budget.overassigned') : ''}
          </p>
        </div>
        <div className="card p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            {t('budget.income_month', { month })}
          </p>
          <p className="mt-1 text-2xl font-bold">
            <Money cents={budget.income} currency={currency} />
          </p>
        </div>
        <div className="card p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{t('budget.assigned')}</p>
          <p className="mt-1 text-2xl font-bold">
            <Money cents={budget.assigned_total} currency={currency} />
          </p>
        </div>
      </div>

      {showAutofill && (
        <div className="card flex flex-wrap items-center gap-3 border-emerald-200 p-4 dark:border-emerald-900">
          <Wand2 className="h-4 w-4 text-emerald-500" />
          <p className="text-sm text-slate-600 dark:text-slate-300">{t('budget.autofill_hint')}</p>
          <button
            className="btn-primary ml-auto"
            disabled={applyAutofill.isPending || (autofill?.suggestions.length ?? 0) === 0}
            onClick={() => applyAutofill.mutate(month)}
          >
            {t('budget.autofill_apply')} ({autofill?.suggestions.length ?? 0})
          </button>
        </div>
      )}

      <div className="card overflow-x-auto">
        {rows.length === 0 ? (
          <p className="p-6 text-center text-sm text-slate-500">{t('budget.no_categories')}</p>
        ) : (
          <table className="w-full min-w-[560px] text-left">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-400 dark:border-slate-800">
                <th className="px-3 py-2">{t('common.category')}</th>
                <th className="px-3 py-2 text-right">{t('budget.assigned')}</th>
                <th className="hidden px-3 py-2 text-right sm:table-cell">{t('budget.activity')}</th>
                <th className="px-3 py-2 text-right">{t('budget.available')}</th>
                <th className="w-10 px-2 py-2" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
              {rows.map((row) => {
                const suggestion = suggestionMap.get(row.category_id)
                const overspent = row.available < 0
                return (
                  <tr key={row.category_id} className={overspent ? 'bg-red-50/60 dark:bg-red-950/20' : ''}>
                    <td className="px-3 py-2">
                      <div className={`flex items-center gap-2 ${row.parent_id ? 'pl-5' : ''}`}>
                        <span>{row.icon}</span>
                        <span className="text-sm font-medium">{row.name}</span>
                        {row.archived && (
                          <span className="badge bg-slate-100 text-slate-400 dark:bg-slate-800">
                            {t('common.archived')}
                          </span>
                        )}
                      </div>
                      {showAutofill && suggestion !== undefined && (
                        <p className="pl-7 text-xs text-emerald-600 dark:text-emerald-400">
                          → {fmtNumber(suggestion)}
                        </p>
                      )}
                      {overspent && (
                        <button
                          className="pl-7 text-left text-xs text-red-600 hover:underline dark:text-red-400"
                          onClick={() => openMove(row.category_id)}
                        >
                          {t('budget.overspent_hint')}
                        </button>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <AssignCell row={row} month={month} currency={currency} />
                    </td>
                    <td className="hidden px-3 py-2 text-right text-sm text-slate-500 sm:table-cell">
                      {fmtNumber(row.activity)}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <span
                        className={`badge tabular-nums ${
                          overspent
                            ? 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-400'
                            : row.available > 0
                              ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400'
                              : 'bg-slate-100 text-slate-500 dark:bg-slate-800'
                        }`}
                      >
                        {fmtNumber(row.available)}
                      </span>
                    </td>
                    <td className="px-2 py-2 text-right">
                      <button
                        className="btn-ghost"
                        title={row.rollover ? t('budget.rollover_on') : t('budget.rollover_off')}
                        onClick={() =>
                          updateCategory.mutate({ id: row.category_id, rollover: !row.rollover })
                        }
                      >
                        {row.rollover ? (
                          <RotateCw className="h-3.5 w-3.5 text-emerald-500" />
                        ) : (
                          <RotateCcw className="h-3.5 w-3.5 text-slate-400" />
                        )}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      <Modal open={moveOpen} onClose={() => setMoveOpen(false)} title={t('budget.move')}>
        <form onSubmit={submitMove} className="space-y-4">
          <div>
            <label className="label">{t('budget.move_from')}</label>
            <select className="input" value={moveFrom} onChange={(e) => setMoveFrom(e.target.value)}>
              <option value="">💰 {t('budget.move_tbb')}</option>
              {rows.map((r) => (
                <option key={r.category_id} value={r.category_id}>
                  {r.icon} {r.name} ({fmtNumber(r.available)})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">{t('budget.move_to')}</label>
            <select className="input" value={moveTo} onChange={(e) => setMoveTo(e.target.value)}>
              <option value="">💰 {t('budget.move_tbb')}</option>
              {rows.map((r) => (
                <option key={r.category_id} value={r.category_id}>
                  {r.icon} {r.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">
              {t('common.amount')} ({currency})
            </label>
            <input
              className="input"
              inputMode="decimal"
              placeholder="0.00"
              value={moveAmountText}
              onChange={(e) => setMoveAmountText(e.target.value)}
            />
          </div>
          {moveError && <p className="text-sm text-red-500">{moveError}</p>}
          <div className="flex justify-end gap-2">
            <button type="button" className="btn-secondary" onClick={() => setMoveOpen(false)}>
              {t('common.cancel')}
            </button>
            <button className="btn-primary" disabled={moveBudget.isPending}>
              {t('common.apply')}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
