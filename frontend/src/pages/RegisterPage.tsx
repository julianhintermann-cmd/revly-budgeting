import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { AuthShell } from '@/components/AuthShell'
import { api, ApiError } from '@/lib/api'
import type { TokenPair } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'

const CURRENCIES = ['CHF', 'EUR', 'USD', 'GBP']

export function RegisterPage() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const { code } = useParams()
  const status = useAuthStore((s) => s.status)
  const setAuth = useAuthStore((s) => s.setAuth)

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [householdName, setHouseholdName] = useState('')
  const [currency, setCurrency] = useState('CHF')
  const [withInvite, setWithInvite] = useState(Boolean(code))
  const [inviteCode, setInviteCode] = useState(code ?? '')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (status === 'authed') navigate('/', { replace: true })
  }, [status, navigate])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const res = await api<TokenPair>('/auth/register', {
        method: 'POST',
        body: {
          name,
          email,
          password,
          locale: i18n.language === 'en' ? 'en' : 'de',
          ...(withInvite
            ? { invite_code: inviteCode.trim() }
            : { household_name: householdName || undefined, currency }),
        },
      })
      setAuth(res)
      navigate(withInvite ? '/' : '/onboarding')
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setError(t('auth.email_taken'))
      else if (err instanceof ApiError && err.status === 422 && err.detail.toLowerCase().includes('invite'))
        setError(t('auth.invite_invalid'))
      else if (err instanceof ApiError) setError(err.detail)
      else setError(t('common.error'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell title={t('auth.register_title')}>
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="label">{t('auth.name')}</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} required />
        </div>
        <div>
          <label className="label">{t('auth.email')}</label>
          <input
            type="email"
            className="input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
        </div>
        <div>
          <label className="label">{t('auth.password')}</label>
          <input
            type="password"
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
          />
          <p className="mt-1 text-xs text-slate-400">{t('auth.password_hint')}</p>
        </div>

        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={withInvite} onChange={(e) => setWithInvite(e.target.checked)} />
          {t('auth.have_invite')}
        </label>

        {withInvite ? (
          <div>
            <label className="label">{t('auth.invite_code')}</label>
            <input
              className="input"
              value={inviteCode}
              onChange={(e) => setInviteCode(e.target.value)}
              required
            />
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-3">
            <div className="col-span-2">
              <label className="label">
                {t('auth.household_name')} ({t('common.optional')})
              </label>
              <input
                className="input"
                placeholder={t('auth.household_placeholder')}
                value={householdName}
                onChange={(e) => setHouseholdName(e.target.value)}
              />
            </div>
            <div>
              <label className="label">{t('auth.base_currency')}</label>
              <select className="input" value={currency} onChange={(e) => setCurrency(e.target.value)}>
                {CURRENCIES.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>
        )}

        {error && <p className="text-sm text-red-500">{error}</p>}
        <button className="btn-primary w-full" disabled={busy}>
          {t('auth.register')}
        </button>
        <p className="text-center text-sm">
          <Link className="text-emerald-600 hover:underline dark:text-emerald-400" to="/login">
            {t('auth.have_account')}
          </Link>
        </p>
      </form>
    </AuthShell>
  )
}
