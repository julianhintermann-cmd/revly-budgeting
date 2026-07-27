import { Paperclip, SlidersHorizontal } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams } from 'react-router-dom'

import { CategorySelect } from '@/components/CategorySelect'
import { EmptyState } from '@/components/EmptyState'
import { Money } from '@/components/Money'
import { Spinner } from '@/components/Spinner'
import {
  useAccounts,
  useBulkAction,
  useCategories,
  useTags,
  useTransactions,
} from '@/hooks/queries'
import { fmtDate, parseAmountInput } from '@/lib/format'
import type { Transaction, TxnFilters, TxnStatus } from '@/lib/types'
import { useUiStore } from '@/stores/ui'

const PAGE_SIZE = 50

export function TransactionsPage() {
  const { t } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const openTxnModal = useUiStore((s) => s.openTxnModal)

  const [showFilters, setShowFilters] = useState(false)
  const [page, setPage] = useState(1)
  const [accountId, setAccountId] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [tag, setTag] = useState('')
  const [status, setStatus] = useState('')
  const [type, setType] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [minText, setMinText] = useState('')
  const [maxText, setMaxText] = useState('')
  const [uncategorized, setUncategorized] = useState(false)
  const [selected, setSelected] = useState<Set<number>>(new Set())

  const [bulkCategory, setBulkCategory] = useState('')
  const [bulkTag, setBulkTag] = useState('')
  const [bulkStatus, setBulkStatus] = useState<TxnStatus>('cleared')

  const q = searchParams.get('q') ?? ''

  const filters: TxnFilters = useMemo(
    () => ({
      q: q || undefined,
      account_id: accountId ? Number(accountId) : undefined,
      category_id: categoryId ? Number(categoryId) : undefined,
      tag: tag || undefined,
      status: (status || undefined) as TxnStatus | undefined,
      type: (type || undefined) as 'in' | 'out' | undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
      min_amount: minText ? (parseAmountInput(minText) ?? undefined) : undefined,
      max_amount: maxText ? (parseAmountInput(maxText) ?? undefined) : undefined,
      uncategorized: uncategorized || undefined,
      page,
      page_size: PAGE_SIZE,
    }),
    [q, accountId, categoryId, tag, status, type, dateFrom, dateTo, minText, maxText, uncategorized, page]
  )

  const { data, isLoading } = useTransactions(filters)
  const { data: accounts } = useAccounts()
  const { data: categories } = useCategories()
  const { data: tags } = useTags()
  const bulk = useBulkAction()

  const catMap = useMemo(() => new Map((categories ?? []).map((c) => [c.id, c])), [categories])
  const accMap = useMemo(() => new Map((accounts ?? []).map((a) => [a.id, a])), [accounts])

  const pages = Math.max(1, Math.ceil((data?.total ?? 0) / PAGE_SIZE))
  const allSelected = (data?.items.length ?? 0) > 0 && data?.items.every((txn) => selected.has(txn.id))

  const toggleAll = () => {
    if (allSelected) setSelected(new Set())
    else setSelected(new Set(data?.items.map((txn) => txn.id) ?? []))
  }

  const toggleOne = (id: number) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setSelected(next)
  }

  const runBulk = async (action: string, extra: Record<string, unknown> = {}) => {
    if (selected.size === 0) return
    if (action === 'delete' && !window.confirm(t('common.confirm_delete'))) return
    await bulk.mutateAsync({ ids: [...selected], action, ...extra })
    setSelected(new Set())
  }

  const statusBadge = (s: TxnStatus) => {
    const styles: Record<TxnStatus, string> = {
      pending: 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-400',
      cleared: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
      reconciled: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400',
    }
    return <span className={`badge ${styles[s]}`}>{t(`transactions.statuses.${s}`)}</span>
  }

  const categoryCell = (txn: Transaction) => {
    if (txn.transfer_group)
      return (
        <span className="badge bg-blue-100 text-blue-700 dark:bg-blue-500/15 dark:text-blue-400">
          🔁 {t('transactions.transfer_badge')}
        </span>
      )
    if (txn.is_split)
      return (
        <span className="text-xs text-slate-500">
          {txn.splits
            .map((s) => {
              const c = s.category_id ? catMap.get(s.category_id) : null
              return c ? `${c.icon} ${c.name}` : '—'
            })
            .join(', ')}
        </span>
      )
    const cat = txn.category_id ? catMap.get(txn.category_id) : null
    if (!cat) return <span className="text-xs text-slate-400">{t('transactions.uncategorized_short')}</span>
    return (
      <span className="text-sm">
        {cat.icon} {cat.name}
      </span>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-bold">{t('transactions.title')}</h1>
        <div className="flex-1" />
        <button className="btn-secondary" onClick={() => setShowFilters((v) => !v)}>
          <SlidersHorizontal className="h-4 w-4" /> {t('common.filter')}
        </button>
        <button className="btn-primary" onClick={() => openTxnModal()}>
          {t('transactions.new')}
        </button>
      </div>

      {q && (
        <p className="text-sm text-slate-500">
          {t('common.search')} „{q}“ –{' '}
          <button className="text-emerald-600 hover:underline" onClick={() => setSearchParams({})}>
            ✕
          </button>
        </p>
      )}

      {showFilters && (
        <div className="card grid grid-cols-2 gap-3 p-4 md:grid-cols-4">
          <div>
            <label className="label">{t('common.account')}</label>
            <select className="input" value={accountId} onChange={(e) => { setAccountId(e.target.value); setPage(1) }}>
              <option value="">{t('common.all')}</option>
              {accounts?.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">{t('common.category')}</label>
            <CategorySelect
              categories={categories ?? []}
              value={categoryId}
              onChange={(v) => { setCategoryId(v); setPage(1) }}
            />
          </div>
          <div>
            <label className="label">{t('common.tags')}</label>
            <select className="input" value={tag} onChange={(e) => { setTag(e.target.value); setPage(1) }}>
              <option value="">{t('common.all')}</option>
              {tags?.map((tg) => (
                <option key={tg.id} value={tg.name}>
                  {tg.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">{t('common.status')}</label>
            <select className="input" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1) }}>
              <option value="">{t('common.all')}</option>
              {(['pending', 'cleared', 'reconciled'] as const).map((s) => (
                <option key={s} value={s}>
                  {t(`transactions.statuses.${s}`)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label">{t('common.from')}</label>
            <input type="date" className="input" value={dateFrom} onChange={(e) => { setDateFrom(e.target.value); setPage(1) }} />
          </div>
          <div>
            <label className="label">{t('common.to')}</label>
            <input type="date" className="input" value={dateTo} onChange={(e) => { setDateTo(e.target.value); setPage(1) }} />
          </div>
          <div>
            <label className="label">{t('transactions.min_amount')}</label>
            <input className="input" inputMode="decimal" value={minText} onChange={(e) => { setMinText(e.target.value); setPage(1) }} />
          </div>
          <div>
            <label className="label">{t('transactions.max_amount')}</label>
            <input className="input" inputMode="decimal" value={maxText} onChange={(e) => { setMaxText(e.target.value); setPage(1) }} />
          </div>
          <div className="col-span-2 flex flex-wrap items-center gap-4 md:col-span-4">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={type === 'in'} onChange={(e) => { setType(e.target.checked ? 'in' : ''); setPage(1) }} />
              {t('transactions.only_in')}
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={type === 'out'} onChange={(e) => { setType(e.target.checked ? 'out' : ''); setPage(1) }} />
              {t('transactions.only_out')}
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={uncategorized} onChange={(e) => { setUncategorized(e.target.checked); setPage(1) }} />
              {t('transactions.uncategorized')}
            </label>
            <span className="ml-auto text-sm text-slate-500">
              {t('transactions.sum_filtered')}: <Money cents={data?.sum_amount ?? 0} colored />
            </span>
          </div>
        </div>
      )}

      {selected.size > 0 && (
        <div className="card flex flex-wrap items-center gap-2 p-3">
          <span className="text-sm font-medium">{t('transactions.selected', { count: selected.size })}</span>
          <CategorySelect
            categories={categories ?? []}
            value={bulkCategory}
            onChange={setBulkCategory}
            className="input w-48"
          />
          <button
            className="btn-secondary"
            disabled={!bulkCategory || bulk.isPending}
            onClick={() => void runBulk('set_category', { category_id: Number(bulkCategory) })}
          >
            {t('transactions.set_category')}
          </button>
          <input
            className="input w-32"
            placeholder="#tag"
            value={bulkTag}
            onChange={(e) => setBulkTag(e.target.value)}
          />
          <button
            className="btn-secondary"
            disabled={!bulkTag.trim() || bulk.isPending}
            onClick={() => void runBulk('add_tag', { tag: bulkTag.trim() })}
          >
            {t('transactions.add_tag')}
          </button>
          <select
            className="input w-36"
            value={bulkStatus}
            onChange={(e) => setBulkStatus(e.target.value as TxnStatus)}
          >
            {(['pending', 'cleared', 'reconciled'] as const).map((s) => (
              <option key={s} value={s}>
                {t(`transactions.statuses.${s}`)}
              </option>
            ))}
          </select>
          <button
            className="btn-secondary"
            disabled={bulk.isPending}
            onClick={() => void runBulk('set_status', { status: bulkStatus })}
          >
            {t('transactions.set_status')}
          </button>
          <button className="btn-danger ml-auto" disabled={bulk.isPending} onClick={() => void runBulk('delete')}>
            {t('transactions.delete_selected')}
          </button>
        </div>
      )}

      <div className="card overflow-x-auto">
        {isLoading ? (
          <Spinner />
        ) : (data?.items.length ?? 0) === 0 ? (
          <EmptyState text={t('transactions.no_results')} />
        ) : (
          <table className="w-full min-w-[640px] text-left">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-400 dark:border-slate-800">
                <th className="w-8 px-3 py-2">
                  <input type="checkbox" checked={allSelected} onChange={toggleAll} />
                </th>
                <th className="px-3 py-2">{t('common.date')}</th>
                <th className="px-3 py-2">{t('transactions.payee')}</th>
                <th className="px-3 py-2">{t('common.category')}</th>
                <th className="px-3 py-2">{t('common.account')}</th>
                <th className="px-3 py-2">{t('common.status')}</th>
                <th className="px-3 py-2 text-right">{t('common.amount')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
              {data?.items.map((txn) => (
                <tr
                  key={txn.id}
                  className="cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/40"
                  onClick={() => openTxnModal(txn)}
                >
                  <td className="px-3 py-2" onClick={(e) => e.stopPropagation()}>
                    <input type="checkbox" checked={selected.has(txn.id)} onChange={() => toggleOne(txn.id)} />
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-sm text-slate-500">{fmtDate(txn.date)}</td>
                  <td className="max-w-48 px-3 py-2">
                    <div className="flex items-center gap-1.5">
                      <span className="truncate text-sm font-medium">{txn.payee || '—'}</span>
                      {txn.has_receipt && <Paperclip className="h-3.5 w-3.5 shrink-0 text-slate-400" />}
                    </div>
                    {txn.tags.length > 0 && (
                      <div className="mt-0.5 flex flex-wrap gap-1">
                        {txn.tags.map((tg) => (
                          <span key={tg} className="badge bg-slate-100 text-slate-500 dark:bg-slate-800">
                            #{tg}
                          </span>
                        ))}
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-2">{categoryCell(txn)}</td>
                  <td className="px-3 py-2 text-sm text-slate-500">{accMap.get(txn.account_id)?.name ?? '—'}</td>
                  <td className="px-3 py-2">{statusBadge(txn.status)}</td>
                  <td className="px-3 py-2 text-right">
                    <Money
                      cents={txn.amount}
                      currency={accMap.get(txn.account_id)?.currency ?? 'CHF'}
                      colored
                      className="text-sm font-semibold"
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="flex items-center justify-between text-sm text-slate-500">
        <span>
          {data?.total ?? 0} {t('transactions.title')}
        </span>
        <div className="flex items-center gap-2">
          <button className="btn-secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            {t('transactions.prev')}
          </button>
          <span>{t('transactions.page_info', { page, pages })}</span>
          <button className="btn-secondary" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>
            {t('transactions.next')}
          </button>
        </div>
      </div>
    </div>
  )
}
