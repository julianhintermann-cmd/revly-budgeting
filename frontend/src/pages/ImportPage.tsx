import { FileUp } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { CategorySelect } from '@/components/CategorySelect'
import { useAccounts, useCategories, useImportCommit, useImportPreview } from '@/hooks/queries'
import type { ImportPreview, ImportResult } from '@/lib/types'

export function ImportPage() {
  const { t } = useTranslation()
  const { data: accounts } = useAccounts()
  const { data: categories } = useCategories()
  const previewMutation = useImportPreview()
  const commitMutation = useImportCommit()

  const [step, setStep] = useState<1 | 2 | 3>(1)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [result, setResult] = useState<ImportResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [accountId, setAccountId] = useState('')
  const [mapDate, setMapDate] = useState('')
  const [mapAmount, setMapAmount] = useState('')
  const [mapPayee, setMapPayee] = useState('')
  const [mapNotes, setMapNotes] = useState('')
  const [dateFormat, setDateFormat] = useState('')
  const [decimalComma, setDecimalComma] = useState<'auto' | 'yes' | 'no'>('auto')
  const [invert, setInvert] = useState(false)
  const [skipDuplicates, setSkipDuplicates] = useState(true)
  const [defaultCategory, setDefaultCategory] = useState('')

  const guessColumn = (columns: string[], needles: string[]): string => {
    const lower = columns.map((c) => c.toLowerCase())
    for (const needle of needles) {
      const idx = lower.findIndex((c) => c.includes(needle))
      if (idx >= 0) return columns[idx]
    }
    return ''
  }

  const onFile = async (file: File | undefined) => {
    if (!file) return
    setError(null)
    try {
      const res = await previewMutation.mutateAsync(file)
      setPreview(res)
      if (res.format === 'csv') {
        setMapDate(guessColumn(res.columns, ['datum', 'date', 'buchung', 'valuta']))
        setMapAmount(guessColumn(res.columns, ['betrag', 'amount', 'summe', 'value']))
        setMapPayee(guessColumn(res.columns, ['empfänger', 'payee', 'name', 'beschreibung', 'description', 'text']))
        setMapNotes(guessColumn(res.columns, ['notiz', 'memo', 'verwendungszweck', 'reference']))
      }
      setStep(2)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    }
  }

  const commit = async () => {
    if (!preview) return
    setError(null)
    try {
      const res = await commitMutation.mutateAsync({
        cache_id: preview.cache_id,
        account_id: Number(accountId),
        ...(preview.format === 'csv'
          ? {
              mapping: {
                date: mapDate,
                amount: mapAmount,
                payee: mapPayee || null,
                notes: mapNotes || null,
              },
              date_format: dateFormat || null,
              decimal_comma: decimalComma === 'auto' ? null : decimalComma === 'yes',
            }
          : {}),
        invert_amounts: invert,
        skip_duplicates: skipDuplicates,
        default_category_id: defaultCategory ? Number(defaultCategory) : null,
      })
      setResult(res)
      setStep(3)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    }
  }

  const reset = () => {
    setStep(1)
    setPreview(null)
    setResult(null)
    setError(null)
    setAccountId('')
  }

  const mappingValid =
    accountId && (preview?.format !== 'csv' || (mapDate && mapAmount))

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-xl font-bold">{t('imports.title')}</h1>

      <div className="flex gap-2 text-xs font-medium">
        {[t('imports.step_upload'), t('imports.step_map'), t('imports.step_done')].map((label, i) => (
          <span
            key={label}
            className={`rounded-full px-3 py-1 ${
              step === i + 1
                ? 'bg-emerald-600 text-white'
                : step > i + 1
                  ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400'
                  : 'bg-slate-100 text-slate-400 dark:bg-slate-800'
            }`}
          >
            {label}
          </span>
        ))}
      </div>

      {step === 1 && (
        <label className="card flex cursor-pointer flex-col items-center gap-3 border-2 border-dashed border-slate-300 p-10 text-center hover:border-emerald-400 dark:border-slate-700">
          <FileUp className="h-8 w-8 text-slate-400" />
          <span className="font-medium">{t('imports.upload')}</span>
          <span className="text-sm text-slate-400">{t('imports.file_hint')}</span>
          <input
            type="file"
            accept=".csv,.ofx,.qfx,.qif,text/csv"
            className="hidden"
            onChange={(e) => void onFile(e.target.files?.[0])}
          />
          {previewMutation.isPending && <span className="text-sm text-slate-400">{t('common.loading')}</span>}
        </label>
      )}

      {step === 2 && preview && (
        <div className="card space-y-4 p-5">
          <p className="text-sm text-emerald-600 dark:text-emerald-400">
            {t('imports.detected', { count: preview.row_count, format: preview.format.toUpperCase() })}
          </p>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">{t('imports.target_account')}</label>
              <select className="input" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
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
              <label className="label">{t('imports.default_category')}</label>
              <CategorySelect categories={categories ?? []} value={defaultCategory} onChange={setDefaultCategory} />
            </div>
          </div>

          {preview.format === 'csv' && (
            <div className="grid grid-cols-2 gap-3">
              {(
                [
                  ['map_date', mapDate, setMapDate],
                  ['map_amount', mapAmount, setMapAmount],
                  ['map_payee', mapPayee, setMapPayee],
                  ['map_notes', mapNotes, setMapNotes],
                ] as const
              ).map(([key, value, setter]) => (
                <div key={key}>
                  <label className="label">{t(`imports.${key}`)}</label>
                  <select className="input" value={value} onChange={(e) => setter(e.target.value)}>
                    <option value="">–</option>
                    {preview.columns.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
              <div>
                <label className="label">
                  {t('imports.decimal_comma')}
                </label>
                <select
                  className="input"
                  value={decimalComma}
                  onChange={(e) => setDecimalComma(e.target.value as 'auto' | 'yes' | 'no')}
                >
                  <option value="auto">{t('imports.auto')}</option>
                  <option value="yes">{t('common.yes')}</option>
                  <option value="no">{t('common.no')}</option>
                </select>
              </div>
              <div>
                <label className="label">
                  {t('common.date')}-Format ({t('common.optional')}): %d.%m.%Y
                </label>
                <input className="input" value={dateFormat} onChange={(e) => setDateFormat(e.target.value)} />
              </div>
            </div>
          )}

          <div className="flex flex-wrap gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={skipDuplicates} onChange={(e) => setSkipDuplicates(e.target.checked)} />
              {t('imports.skip_duplicates')}
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={invert} onChange={(e) => setInvert(e.target.checked)} />
              {t('imports.invert')}
            </label>
          </div>

          <div>
            <p className="label">{t('imports.preview')}</p>
            <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 dark:border-slate-800 dark:bg-slate-800/50">
                    {preview.columns.map((c) => (
                      <th key={c} className="px-2 py-1.5 font-medium">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800/60">
                  {preview.rows.slice(0, 5).map((row, i) => (
                    <tr key={i}>
                      {preview.columns.map((c) => (
                        <td key={c} className="max-w-40 truncate px-2 py-1.5">
                          {row[c]}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex justify-between">
            <button className="btn-secondary" onClick={reset}>
              {t('common.back')}
            </button>
            <button className="btn-primary" disabled={!mappingValid || commitMutation.isPending} onClick={() => void commit()}>
              {t('imports.run_import')}
            </button>
          </div>
        </div>
      )}

      {step === 3 && result && (
        <div className="card space-y-4 p-8 text-center">
          <span className="text-4xl">✅</span>
          <p className="font-medium">
            {t('imports.result', {
              imported: result.imported,
              duplicates: result.duplicates_skipped,
              errors: result.errors,
            })}
          </p>
          <div className="flex justify-center gap-2">
            <button className="btn-secondary" onClick={reset}>
              {t('imports.title')}
            </button>
            <Link to="/transactions" className="btn-primary">
              {t('transactions.title')}
            </Link>
          </div>
        </div>
      )}

      {step === 1 && error && <p className="text-sm text-red-500">{error}</p>}
    </div>
  )
}
