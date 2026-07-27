import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { AuthShell } from '@/components/AuthShell'
import { api, ApiError } from '@/lib/api'
import type { TokenPair, TwoFARequired } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'

export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const status = useAuthStore((s) => s.status)
  const setAuth = useAuthStore((s) => s.setAuth)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [twofa, setTwofa] = useState<TwoFARequired | null>(null)
  const [code, setCode] = useState('')
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
      const res = await api<TokenPair | TwoFARequired>('/auth/login', {
        method: 'POST',
        body: { email, password },
      })
      if ('requires_2fa' in res) {
        setTwofa(res)
      } else {
        setAuth(res)
        navigate('/')
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) setError(t('auth.rate_limited'))
      else setError(t('auth.failed'))
    } finally {
      setBusy(false)
    }
  }

  const verify = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!twofa) return
    setError(null)
    setBusy(true)
    try {
      const res = await api<TokenPair>('/auth/2fa/verify', {
        method: 'POST',
        body: { temp_token: twofa.temp_token, code },
      })
      setAuth(res)
      navigate('/')
    } catch (err) {
      if (err instanceof ApiError && err.status === 401 && err.detail.includes('session')) {
        setTwofa(null)
      }
      setError(t('auth.failed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell title={twofa ? t('auth.twofa_title') : t('auth.login_title')}>
      {!twofa ? (
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label" htmlFor="email">
              {t('auth.email')}
            </label>
            <input
              id="email"
              type="email"
              className="input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>
          <div>
            <label className="label" htmlFor="password">
              {t('auth.password')}
            </label>
            <input
              id="password"
              type="password"
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>
          {error && <p className="text-sm text-red-500">{error}</p>}
          <button className="btn-primary w-full" disabled={busy}>
            {t('auth.login')}
          </button>
          <p className="text-center text-sm">
            <Link className="text-emerald-600 hover:underline dark:text-emerald-400" to="/register">
              {t('auth.no_account')}
            </Link>
          </p>
        </form>
      ) : (
        <form onSubmit={verify} className="space-y-4">
          <p className="text-sm text-slate-500 dark:text-slate-400">{t('auth.twofa_hint')}</p>
          <input
            className="input text-center text-lg tracking-[0.4em]"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            inputMode="numeric"
            maxLength={6}
            autoFocus
          />
          {error && <p className="text-sm text-red-500">{error}</p>}
          <button className="btn-primary w-full" disabled={busy || code.length < 6}>
            {t('auth.verify')}
          </button>
        </form>
      )}
    </AuthShell>
  )
}
