import { zodResolver } from '@hookform/resolvers/zod'
import { Paperclip, Plus, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useFieldArray, useForm } from 'react-hook-form'
import { useTranslation } from 'react-i18next'
import { z } from 'zod'

import { CategorySelect } from '@/components/CategorySelect'
import { Modal } from '@/components/Modal'
import { Money } from '@/components/Money'
import {
  useAccounts,
  useCategories,
  useCreateTransaction,
  useUpdateTransaction,
  useUploadReceipt,
} from '@/hooks/queries'
import { openBlobInTab } from '@/lib/api'
import { centsToInput, parseAmountInput, todayISO } from '@/lib/format'
import type { Transaction } from '@/lib/types'
import { useUiStore } from '@/stores/ui'

const schema = z
  .object({
    kind: z.enum(['expense', 'income', 'transfer']),
    account_id: z.string().min(1),
    transfer_to: z.string(),
    date: z.string().min(8),
    amountText: z.string().refine((v) => (parseAmountInput(v) ?? 0) > 0),
    payee: z.string().max(200),
    category_id: z.string(),
    status: z.enum(['pending', 'cleared', 'reconciled']),
    notes: z.string().max(2000),
    tagsText: z.string(),
    splitMode: z.boolean(),
    splits: z.array(
      z.object({ category_id: z.string(), amountText: z.string(), note: z.string() })
    ),
  })
  .superRefine((v, ctx) => {
    if (v.kind === 'transfer') {
      if (!v.transfer_to) ctx.addIssue({ code: 'custom', path: ['transfer_to'], message: 'required' })
      else if (v.transfer_to === v.account_id)
        ctx.addIssue({ code: 'custom', path: ['transfer_to'], message: 'same' })
    }
    if (v.splitMode && v.kind !== 'transfer') {
      if (v.splits.length < 2) {
        ctx.addIssue({ code: 'custom', path: ['splitMode'], message: 'min2' })
        return
      }
      const total = parseAmountInput(v.amountText) ?? 0
      let sum = 0
      v.splits.forEach((s, i) => {
        const cents = parseAmountInput(s.amountText)
        if (cents === null || cents <= 0)
          ctx.addIssue({ code: 'custom', path: ['splits', i, 'amountText'], message: 'amount' })
        else sum += cents
      })
      if (sum !== total) ctx.addIssue({ code: 'custom', path: ['splitMode'], message: 'sum' })
    }
  })

type FormValues = z.infer<typeof schema>

function defaultValues(txn: Transaction | null, defaultAccountId?: number): FormValues {
  if (txn) {
    return {
      kind: txn.transfer_group ? 'transfer' : txn.amount >= 0 ? 'income' : 'expense',
      account_id: String(txn.account_id),
      transfer_to: txn.transfer_account_id ? String(txn.transfer_account_id) : '',
      date: txn.date,
      amountText: centsToInput(txn.amount),
      payee: txn.payee,
      category_id: txn.category_id ? String(txn.category_id) : '',
      status: txn.status,
      notes: txn.notes,
      tagsText: txn.tags.join(', '),
      splitMode: txn.is_split,
      splits: txn.splits.map((s) => ({
        category_id: s.category_id ? String(s.category_id) : '',
        amountText: centsToInput(s.amount),
        note: s.note,
      })),
    }
  }
  return {
    kind: 'expense',
    account_id: defaultAccountId ? String(defaultAccountId) : '',
    transfer_to: '',
    date: todayISO(),
    amountText: '',
    payee: '',
    category_id: '',
    status: 'cleared',
    notes: '',
    tagsText: '',
    splitMode: false,
    splits: [],
  }
}

export function TransactionFormModal() {
  const { t } = useTranslation()
  const { open, txn, defaultAccountId } = useUiStore((s) => s.txnModal)
  const closeTxnModal = useUiStore((s) => s.closeTxnModal)
  const { data: accounts } = useAccounts()
  const { data: categories } = useCategories()
  const createTxn = useCreateTransaction()
  const updateTxn = useUpdateTransaction()
  const uploadReceipt = useUploadReceipt()
  const [apiError, setApiError] = useState<string | null>(null)

  const activeAccounts = useMemo(() => (accounts ?? []).filter((a) => !a.archived), [accounts])
  const editing = txn ?? null
  const isTransferEdit = Boolean(editing?.transfer_group)

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: defaultValues(editing, defaultAccountId),
  })
  const { register, handleSubmit, watch, setValue, control, reset, formState } = form
  const { fields, append, remove } = useFieldArray({ control, name: 'splits' })

  useEffect(() => {
    if (open) {
      reset(defaultValues(editing, defaultAccountId))
      setApiError(null)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, editing?.id])

  const kind = watch('kind')
  const splitMode = watch('splitMode')
  const amountText = watch('amountText')
  const splits = watch('splits')
  const accountId = watch('account_id')

  const currency = activeAccounts.find((a) => String(a.id) === accountId)?.currency ?? 'CHF'
  const total = parseAmountInput(amountText) ?? 0
  const splitSum = (splits ?? []).reduce((acc, s) => acc + (parseAmountInput(s.amountText) ?? 0), 0)
  const splitRest = total - splitSum

  const onSubmit = handleSubmit(async (v) => {
    setApiError(null)
    const cents = parseAmountInput(v.amountText)!
    const tags = v.tagsText
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    try {
      if (editing) {
        if (isTransferEdit) {
          await updateTxn.mutateAsync({
            id: editing.id,
            date: v.date,
            amount: editing.amount < 0 ? -cents : cents,
            payee: v.payee,
            notes: v.notes,
            status: v.status,
          })
        } else {
          const signed = v.kind === 'income' ? cents : -cents
          await updateTxn.mutateAsync({
            id: editing.id,
            account_id: Number(v.account_id),
            date: v.date,
            amount: signed,
            payee: v.payee,
            notes: v.notes,
            status: v.status,
            tags,
            ...(v.splitMode
              ? {
                  splits: v.splits.map((s) => ({
                    category_id: s.category_id ? Number(s.category_id) : null,
                    amount:
                      v.kind === 'income'
                        ? parseAmountInput(s.amountText)!
                        : -parseAmountInput(s.amountText)!,
                    note: s.note,
                  })),
                }
              : {
                  ...(editing.is_split ? { clear_splits: true } : {}),
                  ...(v.category_id
                    ? { category_id: Number(v.category_id) }
                    : { clear_category: true }),
                }),
          })
        }
      } else if (v.kind === 'transfer') {
        await createTxn.mutateAsync({
          account_id: Number(v.account_id),
          transfer_to_account_id: Number(v.transfer_to),
          date: v.date,
          amount: cents,
          payee: v.payee,
          notes: v.notes,
          status: v.status,
        })
      } else {
        const signed = v.kind === 'income' ? cents : -cents
        await createTxn.mutateAsync({
          account_id: Number(v.account_id),
          date: v.date,
          amount: signed,
          payee: v.payee,
          notes: v.notes,
          status: v.status,
          tags,
          ...(v.splitMode
            ? {
                splits: v.splits.map((s) => ({
                  category_id: s.category_id ? Number(s.category_id) : null,
                  amount:
                    v.kind === 'income'
                      ? parseAmountInput(s.amountText)!
                      : -parseAmountInput(s.amountText)!,
                  note: s.note,
                })),
              }
            : v.category_id
              ? { category_id: Number(v.category_id) }
              : {}),
        })
      }
      closeTxnModal()
    } catch (err) {
      setApiError(err instanceof Error ? err.message : String(err))
    }
  })

  const onReceiptChange = async (file: File | undefined) => {
    if (!file || !editing) return
    try {
      await uploadReceipt.mutateAsync({ id: editing.id, file })
    } catch (err) {
      setApiError(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <Modal
      open={open}
      onClose={closeTxnModal}
      title={editing ? t('transactions.edit') : t('transactions.new')}
      wide
    >
      <form onSubmit={onSubmit} className="space-y-4">
        {!isTransferEdit && (
          <div className="flex gap-1 rounded-lg bg-slate-100 p-1 dark:bg-slate-800">
            {(['expense', 'income', 'transfer'] as const).map((k) => (
              <button
                key={k}
                type="button"
                disabled={Boolean(editing) && k === 'transfer'}
                className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  kind === k
                    ? 'bg-white shadow-sm dark:bg-slate-700'
                    : 'text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                } disabled:opacity-40`}
                onClick={() => setValue('kind', k)}
              >
                {t(`transactions.${k === 'transfer' ? 'transfer' : k}`)}
              </button>
            ))}
          </div>
        )}

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <div>
            <label className="label">{t('common.account')}</label>
            <select className="input" disabled={isTransferEdit} {...register('account_id')}>
              <option value="">–</option>
              {activeAccounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
            {formState.errors.account_id && (
              <p className="mt-1 text-xs text-red-500">{t('common.required')}</p>
            )}
          </div>
          {kind === 'transfer' && !isTransferEdit && (
            <div>
              <label className="label">{t('transactions.transfer_to')}</label>
              <select className="input" {...register('transfer_to')}>
                <option value="">–</option>
                {activeAccounts
                  .filter((a) => String(a.id) !== accountId)
                  .map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
              </select>
              {formState.errors.transfer_to && (
                <p className="mt-1 text-xs text-red-500">{t('common.required')}</p>
              )}
            </div>
          )}
          <div>
            <label className="label">{t('common.date')}</label>
            <input type="date" className="input" {...register('date')} />
          </div>
          <div>
            <label className="label">
              {t('common.amount')} ({currency})
            </label>
            <input className="input" inputMode="decimal" placeholder="0.00" {...register('amountText')} />
            {formState.errors.amountText && (
              <p className="mt-1 text-xs text-red-500">{t('common.required')}</p>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="label">{t('transactions.payee')}</label>
            <input className="input" placeholder={t('transactions.payee_placeholder')} {...register('payee')} />
          </div>
          {kind !== 'transfer' && !splitMode && (
            <div>
              <label className="label">{t('common.category')}</label>
              <CategorySelect
                categories={categories ?? []}
                value={watch('category_id')}
                onChange={(v) => setValue('category_id', v)}
                typeFilter={kind === 'income' ? 'income' : 'expense'}
              />
            </div>
          )}
          <div>
            <label className="label">{t('common.status')}</label>
            <select className="input" {...register('status')}>
              {(['pending', 'cleared', 'reconciled'] as const).map((s) => (
                <option key={s} value={s}>
                  {t(`transactions.statuses.${s}`)}
                </option>
              ))}
            </select>
          </div>
          {kind !== 'transfer' && (
            <div>
              <label className="label">{t('common.tags')}</label>
              <input className="input" placeholder={t('transactions.tags_placeholder')} {...register('tagsText')} />
            </div>
          )}
        </div>

        {kind !== 'transfer' && (
          <div className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 text-sm font-medium">
                <input
                  type="checkbox"
                  checked={splitMode}
                  onChange={(e) => {
                    setValue('splitMode', e.target.checked)
                    if (e.target.checked && fields.length === 0) {
                      append({ category_id: '', amountText: '', note: '' })
                      append({ category_id: '', amountText: '', note: '' })
                    }
                  }}
                />
                {t('transactions.split')}
              </label>
              {splitMode && (
                <span className={`text-xs ${splitRest === 0 ? 'text-emerald-600' : 'text-amber-600'}`}>
                  {t('transactions.split_remaining', { amount: centsToInput(splitRest) })}
                </span>
              )}
            </div>
            {splitMode && (
              <div className="mt-3 space-y-2">
                {fields.map((field, i) => (
                  <div key={field.id} className="flex items-start gap-2">
                    <div className="flex-1">
                      <CategorySelect
                        categories={categories ?? []}
                        value={watch(`splits.${i}.category_id`)}
                        onChange={(v) => setValue(`splits.${i}.category_id`, v)}
                        typeFilter={kind === 'income' ? 'income' : 'expense'}
                      />
                    </div>
                    <input
                      className="input w-28"
                      inputMode="decimal"
                      placeholder="0.00"
                      {...register(`splits.${i}.amountText`)}
                    />
                    <input
                      className="input flex-1"
                      placeholder={t('common.notes')}
                      {...register(`splits.${i}.note`)}
                    />
                    <button type="button" className="btn-ghost" onClick={() => remove(i)}>
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => append({ category_id: '', amountText: '', note: '' })}
                >
                  <Plus className="h-4 w-4" /> {t('transactions.add_split')}
                </button>
                {formState.errors.splitMode && (
                  <p className="text-xs text-red-500">
                    {t('transactions.split_remaining', { amount: centsToInput(splitRest) })}
                  </p>
                )}
              </div>
            )}
          </div>
        )}

        <div>
          <label className="label">{t('common.notes')}</label>
          <textarea className="input" rows={2} {...register('notes')} />
        </div>

        {editing && !isTransferEdit && (
          <div className="flex items-center gap-3 text-sm">
            <Paperclip className="h-4 w-4 text-slate-400" />
            {editing.has_receipt && (
              <button
                type="button"
                className="text-emerald-600 hover:underline dark:text-emerald-400"
                onClick={() => void openBlobInTab(`/transactions/${editing.id}/receipt`)}
              >
                {t('transactions.view_receipt')}
              </button>
            )}
            <label className="cursor-pointer text-slate-500 hover:underline">
              {t('transactions.upload_receipt')}
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp,application/pdf"
                className="hidden"
                onChange={(e) => void onReceiptChange(e.target.files?.[0])}
              />
            </label>
            {uploadReceipt.isPending && <span className="text-xs text-slate-400">…</span>}
          </div>
        )}

        {apiError && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600 dark:bg-red-950/40 dark:text-red-400">
            {apiError}
          </p>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <button type="button" className="btn-secondary" onClick={closeTxnModal}>
            {t('common.cancel')}
          </button>
          <button type="submit" className="btn-primary" disabled={createTxn.isPending || updateTxn.isPending}>
            {t('common.save')}
          </button>
        </div>
      </form>
    </Modal>
  )
}
