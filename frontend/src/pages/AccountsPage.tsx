import { Pencil, Scale } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Modal } from '@/components/Modal'
import { Money } from '@/components/Money'
import { Spinner } from '@/components/Spinner'
import {
  useAccounts,
  useCreateAccount,
  useDeleteAccount,
  useHouseholds,
  useReconcile,
  useUpdateAccount,
} from '@/hooks/queries'
import { ApiError } from '@/lib/api'
import { centsToInput, fmtMoney, parseAmountInput, todayISO } from '@/lib/format'
import type { Account, AccountType } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

const ACCOUNT_TYPES: AccountType[] = ['checking', 'savings', 'credit_card', 'cash', 'loan', 'investment']

export function AccountsPage() {
  const { t } = useTranslation()
  const user = useAuthStore((s) => s.user)
  const openTxnModal = useUiStore((s) => s.openTxnModal)
  const { data: accounts, isLoading } = useAccounts()
  const { data: households } = useHouseholds()
  const createAccount = useCreateAccount()
  const updateAccount = useUpdateAccount()
  const deleteAccount = useDeleteAccount()
  const reconcile = useReconcile()

  const baseCurrency = households?.find((h) => h.id === user?.active_household_id)?.currency ?? 'CHF'

  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<Account | null>(null)
  const [name, setName] = useState('')
  const [type, setType] = useState<AccountType>('checking')
  const [currency, setCurrency] = useState('')
  const [balanceText, setBalanceText] = useState('')
  const [openingDate, setOpeningDate] = useState(todayISO())
  const [note, setNote] = useState('')
  const [archived, setArchived] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [reconcileFor, setReconcileFor] = useState<Account | null>(null)
  const [statementText, setStatementText] = useState('')
  const [reconcileResult, setReconcileResult] = useState<string | null>(null)

  const openForm = (account: Account | null) => {
    setEditing(account)
    setName(account?.name ?? '')
    setType(account?.type ?? 'checking')
    setCurrency(account?.currency ?? baseCurrency)
    setBalanceText(account ? centsToInput(account.initial_balance) : '')
    setOpeningDate(account?.opening_date ?? todayISO())
    setNote(account?.note ?? '')
    setArchived(account?.archived ?? false)
    setError(null)
    setFormOpen(true)
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    const raw = balanceText.trim() ? parseAmountInput(balanceText.replace('-', '')) : 0
    if (raw === null) {
      setError(t('common.required'))
      return
    }
    const initial = balanceText.trim().startsWith('-') ? -raw : raw
    const body = {
      name,
      type,
      currency,
      initial_balance: initial,
      opening_date: openingDate,
      note,
      ...(editing ? { archived } : {}),
    }
    try {
      if (editing) await updateAccount.mutateAsync({ id: editing.id, ...body })
      else await createAccount.mutateAsync(body)
      setFormOpen(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    }
  }

  const remove = async () => {
    if (!editing || !window.confirm(t('common.confirm_delete'))) return
    try {
      await deleteAccount.mutateAsync(editing.id)
      setFormOpen(false)
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setError(t('accounts.delete_blocked'))
      else setError(err instanceof Error ? err.message : t('common.error'))
    }
  }

  const submitReconcile = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!reconcileFor) return
    const cents = parseAmountInput(statementText.replace('-', ''))
    if (cents === null) return
    const signed = statementText.trim().startsWith('-') ? -cents : cents
    const result = await reconcile.mutateAsync({ id: reconcileFor.id, statement_balance: signed })
    setReconcileResult(
      t('accounts.reconcile_done', { diff: fmtMoney(result.difference, reconcileFor.currency) })
    )
  }

  if (isLoading) return <Spinner />

  const active = (accounts ?? []).filter((a) => !a.archived)
  const archivedAccounts = (accounts ?? []).filter((a) => a.archived)
  const totalBase = active.reduce((sum, a) => sum + a.balance_base, 0)

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-bold">{t('accounts.title')}</h1>
        <span className="text-sm text-slate-500">
          {t('dashboard.net_worth')}: <Money cents={totalBase} currency={baseCurrency} colored />
        </span>
        <div className="flex-1" />
        <button className="btn-primary" onClick={() => openForm(null)}>
          {t('accounts.new')}
        </button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {active.map((a) => (
          <div key={a.id} className="card p-4">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-semibold">{a.name}</p>
                <p className="text-xs text-slate-400">
                  {t(`accounts.types.${a.type}`)} · {a.currency}
                </p>
              </div>
              <div className="flex gap-1">
                <button className="btn-ghost" onClick={() => setReconcileFor(a)} title={t('accounts.reconcile')}>
                  <Scale className="h-4 w-4" />
                </button>
                <button className="btn-ghost" onClick={() => openForm(a)} title={t('common.edit')}>
                  <Pencil className="h-4 w-4" />
                </button>
              </div>
            </div>
            <p className="mt-3 text-2xl font-bold">
              <Money cents={a.balance} currency={a.currency} colored />
            </p>
            <p className="text-xs text-slate-400">
              {t('accounts.cleared_balance')}: <Money cents={a.cleared_balance} currency={a.currency} />
              {a.currency !== baseCurrency && (
                <> · {t('accounts.in_base', { amount: fmtMoney(a.balance_base, baseCurrency) })}</>
              )}
            </p>
            <button
              className="mt-3 text-xs text-emerald-600 hover:underline dark:text-emerald-400"
              onClick={() => openTxnModal(null, a.id)}
            >
              + {t('transactions.new')}
            </button>
          </div>
        ))}
      </div>

      {archivedAccounts.length > 0 && (
        <details className="card p-4">
          <summary className="cursor-pointer text-sm font-medium text-slate-500">
            {t('accounts.archived_section')} ({archivedAccounts.length})
          </summary>
          <ul className="mt-2 divide-y divide-slate-100 dark:divide-slate-800">
            {archivedAccounts.map((a) => (
              <li key={a.id} className="flex items-center justify-between py-2 text-sm">
                <span className="text-slate-400">{a.name}</span>
                <div className="flex items-center gap-3">
                  <Money cents={a.balance} currency={a.currency} className="text-slate-400" />
                  <button className="text-xs text-emerald-600 hover:underline" onClick={() => openForm(a)}>
                    {t('common.edit')}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </details>
      )}

      <Modal open={formOpen} onClose={() => setFormOpen(false)} title={editing ? t('accounts.edit') : t('accounts.new')}>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label">{t('common.name')}</label>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} required />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">{t('common.type')}</label>
              <select className="input" value={type} onChange={(e) => setType(e.target.value as AccountType)}>
                {ACCOUNT_TYPES.map((at) => (
                  <option key={at} value={at}>
                    {t(`accounts.types.${at}`)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">{t('common.currency')}</label>
              <input
                className="input uppercase"
                maxLength={3}
                value={currency}
                onChange={(e) => setCurrency(e.target.value.toUpperCase())}
              />
            </div>
            <div>
              <label className="label">{t('accounts.initial_balance')}</label>
              <input
                className="input"
                inputMode="decimal"
                placeholder="0.00"
                value={balanceText}
                onChange={(e) => setBalanceText(e.target.value)}
              />
            </div>
            <div>
              <label className="label">{t('accounts.opening_date')}</label>
              <input type="date" className="input" value={openingDate} onChange={(e) => setOpeningDate(e.target.value)} />
            </div>
          </div>
          <div>
            <label className="label">{t('accounts.note')}</label>
            <input className="input" value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
          {editing && (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} />
              {t('common.archive')}
            </label>
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
              <button className="btn-primary" disabled={createAccount.isPending || updateAccount.isPending}>
                {t('common.save')}
              </button>
            </div>
          </div>
        </form>
      </Modal>

      <Modal
        open={reconcileFor !== null}
        onClose={() => {
          setReconcileFor(null)
          setStatementText('')
          setReconcileResult(null)
        }}
        title={t('accounts.reconcile_title')}
      >
        {reconcileFor && (
          <form onSubmit={submitReconcile} className="space-y-4">
            <p className="text-sm text-slate-500 dark:text-slate-400">{t('accounts.reconcile_hint')}</p>
            <p className="text-sm">
              {reconcileFor.name} – {t('accounts.cleared_balance')}:{' '}
              <Money cents={reconcileFor.cleared_balance} currency={reconcileFor.currency} className="font-semibold" />
            </p>
            <div>
              <label className="label">
                {t('accounts.statement_balance')} ({reconcileFor.currency})
              </label>
              <input
                className="input"
                inputMode="decimal"
                placeholder="0.00"
                value={statementText}
                onChange={(e) => setStatementText(e.target.value)}
                autoFocus
              />
            </div>
            {reconcileResult && (
              <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400">
                {reconcileResult}
              </p>
            )}
            <div className="flex justify-end gap-2">
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  setReconcileFor(null)
                  setStatementText('')
                  setReconcileResult(null)
                }}
              >
                {t('common.close')}
              </button>
              <button className="btn-primary" disabled={reconcile.isPending || !statementText.trim()}>
                {t('accounts.reconcile')}
              </button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  )
}
