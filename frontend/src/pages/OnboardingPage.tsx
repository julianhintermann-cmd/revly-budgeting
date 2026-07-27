import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import { useCategories, useCreateAccount } from '@/hooks/queries'
import { parseAmountInput } from '@/lib/format'
import type { AccountType } from '@/lib/types'

const ACCOUNT_TYPES: AccountType[] = ['checking', 'savings', 'credit_card', 'cash', 'loan', 'investment']

export function OnboardingPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const createAccount = useCreateAccount()
  const { data: categories } = useCategories()

  const [step, setStep] = useState(1)
  const [name, setName] = useState('')
  const [type, setType] = useState<AccountType>('checking')
  const [balanceText, setBalanceText] = useState('')
  const [error, setError] = useState<string | null>(null)

  const createFirstAccount = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    const cents = balanceText.trim() ? parseAmountInput(balanceText) : 0
    if (cents === null) {
      setError(t('common.required'))
      return
    }
    try {
      await createAccount.mutateAsync({ name, type, initial_balance: cents })
      setStep(2)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-lg">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-bold">{t('onboarding.title')}</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">{t('onboarding.subtitle')}</p>
        </div>

        <div className="mb-6 flex justify-center gap-2">
          {[1, 2, 3].map((s) => (
            <div
              key={s}
              className={`h-1.5 w-16 rounded-full ${s <= step ? 'bg-emerald-500' : 'bg-slate-200 dark:bg-slate-800'}`}
            />
          ))}
        </div>

        <div className="card p-6">
          {step === 1 && (
            <form onSubmit={createFirstAccount} className="space-y-4">
              <div>
                <h2 className="font-semibold">{t('onboarding.step1_title')}</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400">{t('onboarding.step1_text')}</p>
              </div>
              <div>
                <label className="label">{t('common.name')}</label>
                <input
                  className="input"
                  placeholder={t('onboarding.account_name_placeholder')}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
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
                  <label className="label">{t('onboarding.current_balance')}</label>
                  <input
                    className="input"
                    inputMode="decimal"
                    placeholder="0.00"
                    value={balanceText}
                    onChange={(e) => setBalanceText(e.target.value)}
                  />
                </div>
              </div>
              {error && <p className="text-sm text-red-500">{error}</p>}
              <div className="flex justify-between">
                <button type="button" className="btn-ghost" onClick={() => navigate('/')}>
                  {t('onboarding.skip')}
                </button>
                <button className="btn-primary" disabled={createAccount.isPending}>
                  {t('common.create')}
                </button>
              </div>
            </form>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <div>
                <h2 className="font-semibold">{t('onboarding.step2_title')}</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400">{t('onboarding.step2_text')}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {(categories ?? [])
                  .filter((c) => !c.archived)
                  .map((c) => (
                    <span key={c.id} className="badge bg-slate-100 dark:bg-slate-800">
                      {c.icon} {c.name}
                    </span>
                  ))}
              </div>
              <p className="text-sm text-emerald-600 dark:text-emerald-400">
                {t('onboarding.categories_ready', { count: (categories ?? []).length })}
              </p>
              <div className="flex justify-end">
                <button className="btn-primary" onClick={() => setStep(3)}>
                  {t('common.done')}
                </button>
              </div>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <div>
                <h2 className="font-semibold">{t('onboarding.step3_title')}</h2>
                <p className="text-sm text-slate-500 dark:text-slate-400">{t('onboarding.step3_text')}</p>
              </div>
              <div className="flex justify-end">
                <button className="btn-primary" onClick={() => navigate('/budget')}>
                  {t('onboarding.go_budget')}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
