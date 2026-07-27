import { QRCodeSVG } from 'qrcode.react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Modal } from '@/components/Modal'
import {
  refreshMe,
  useApiTokens,
  useChangeMemberRole,
  useCreateApiToken,
  useCreateHousehold,
  useCreateInvite,
  useDeleteApiToken,
  useDeleteInvite,
  useHouseholds,
  useInvites,
  useJoinHousehold,
  useMembers,
  useRates,
  useRemoveMember,
  useSaveRates,
  useSaveSmtp,
  useSmtp,
  useSwitchHousehold,
  useTestSmtp,
  useUpdateMe,
} from '@/hooks/queries'
import { setLocale } from '@/i18n'
import { api } from '@/lib/api'
import { fmtDate, fmtDateTime } from '@/lib/format'
import type { Locale, Role } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

type Tab = 'profile' | 'security' | 'household' | 'tokens' | 'rates' | 'smtp'

function ProfileTab() {
  const { t, i18n } = useTranslation()
  const user = useAuthStore((s) => s.user)
  const updateMe = useUpdateMe()
  const theme = useUiStore((s) => s.theme)
  const setTheme = useUiStore((s) => s.setTheme)
  const [name, setName] = useState(user?.name ?? '')
  const [saved, setSaved] = useState(false)

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    await updateMe.mutateAsync({ name })
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const changeLocale = async (locale: Locale) => {
    setLocale(locale)
    await updateMe.mutateAsync({ locale })
  }

  return (
    <div className="space-y-6">
      <form onSubmit={save} className="space-y-4">
        <div>
          <label className="label">{t('auth.name')}</label>
          <input className="input max-w-sm" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <button className="btn-primary" disabled={updateMe.isPending}>
          {t('common.save')}
        </button>
        {saved && <span className="ml-3 text-sm text-emerald-600">{t('settings.profile.saved')}</span>}
      </form>

      <div className="grid max-w-sm gap-4">
        <div>
          <label className="label">{t('settings.profile.language')}</label>
          <select
            className="input"
            value={i18n.language === 'en' ? 'en' : 'de'}
            onChange={(e) => void changeLocale(e.target.value as Locale)}
          >
            <option value="de">Deutsch</option>
            <option value="en">English</option>
          </select>
        </div>
        <div>
          <label className="label">{t('settings.profile.theme')}</label>
          <select className="input" value={theme} onChange={(e) => setTheme(e.target.value as 'light' | 'dark')}>
            <option value="light">{t('settings.profile.theme_light')}</option>
            <option value="dark">{t('settings.profile.theme_dark')}</option>
          </select>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={user?.email_notifications ?? true}
            onChange={(e) => updateMe.mutate({ email_notifications: e.target.checked })}
          />
          {t('settings.profile.email_notifications')}
        </label>
      </div>
    </div>
  )
}

function SecurityTab() {
  const { t } = useTranslation()
  const user = useAuthStore((s) => s.user)
  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [pwMessage, setPwMessage] = useState<string | null>(null)
  const [pwError, setPwError] = useState<string | null>(null)

  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null)
  const [code, setCode] = useState('')
  const [twofaError, setTwofaError] = useState<string | null>(null)
  const [twofaMessage, setTwofaMessage] = useState<string | null>(null)

  const changePassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setPwError(null)
    setPwMessage(null)
    try {
      await api('/users/me/password', {
        method: 'POST',
        body: { current_password: currentPw, new_password: newPw },
      })
      setPwMessage(t('settings.security.password_changed'))
      setCurrentPw('')
      setNewPw('')
    } catch (err) {
      setPwError(err instanceof Error ? err.message : t('common.error'))
    }
  }

  const startSetup = async () => {
    setTwofaError(null)
    const res = await api<{ secret: string; otpauth_uri: string }>('/auth/2fa/setup', { method: 'POST' })
    setSetup(res)
  }

  const enable = async (e: React.FormEvent) => {
    e.preventDefault()
    setTwofaError(null)
    try {
      await api('/auth/2fa/enable', { method: 'POST', body: { code: code.trim() } })
      await refreshMe()
      setSetup(null)
      setCode('')
      setTwofaMessage(t('settings.security.twofa_enabled'))
    } catch (err) {
      setTwofaError(err instanceof Error ? err.message : t('common.error'))
    }
  }

  const disable = async (e: React.FormEvent) => {
    e.preventDefault()
    setTwofaError(null)
    try {
      await api('/auth/2fa/disable', { method: 'POST', body: { code: code.trim() } })
      await refreshMe()
      setCode('')
      setTwofaMessage(t('settings.security.twofa_disabled'))
    } catch (err) {
      setTwofaError(err instanceof Error ? err.message : t('common.error'))
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h3 className="mb-3 font-semibold">{t('settings.security.change_password')}</h3>
        <form onSubmit={changePassword} className="max-w-sm space-y-3">
          <div>
            <label className="label">{t('settings.security.current_password')}</label>
            <input
              type="password"
              className="input"
              value={currentPw}
              onChange={(e) => setCurrentPw(e.target.value)}
              autoComplete="current-password"
              required
            />
          </div>
          <div>
            <label className="label">{t('settings.security.new_password')}</label>
            <input
              type="password"
              className="input"
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              minLength={8}
              autoComplete="new-password"
              required
            />
          </div>
          {pwError && <p className="text-sm text-red-500">{pwError}</p>}
          {pwMessage && <p className="text-sm text-emerald-600">{pwMessage}</p>}
          <button className="btn-primary">{t('common.save')}</button>
        </form>
      </div>

      <div>
        <h3 className="mb-1 font-semibold">{t('settings.security.twofa')}</h3>
        <p className="mb-3 text-sm text-slate-500">
          {user?.totp_enabled ? '✅ ' + t('settings.security.twofa_on') : t('settings.security.twofa_off')}
        </p>
        {twofaMessage && <p className="mb-2 text-sm text-emerald-600">{twofaMessage}</p>}

        {!user?.totp_enabled && !setup && (
          <button className="btn-secondary" onClick={() => void startSetup()}>
            {t('settings.security.twofa_start')}
          </button>
        )}

        {setup && (
          <form onSubmit={enable} className="max-w-sm space-y-3">
            <p className="text-sm text-slate-500">{t('settings.security.twofa_scan')}</p>
            <div className="inline-block rounded-lg bg-white p-3">
              <QRCodeSVG value={setup.otpauth_uri} size={160} />
            </div>
            <p className="break-all text-xs text-slate-400">
              {t('settings.security.twofa_secret')}: <code>{setup.secret}</code>
            </p>
            <div>
              <label className="label">{t('settings.security.twofa_code')}</label>
              <input
                className="input"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                inputMode="numeric"
                maxLength={6}
              />
            </div>
            {twofaError && <p className="text-sm text-red-500">{twofaError}</p>}
            <button className="btn-primary">{t('settings.security.twofa_enable')}</button>
          </form>
        )}

        {user?.totp_enabled && (
          <form onSubmit={disable} className="flex max-w-sm items-end gap-2">
            <div className="flex-1">
              <label className="label">{t('settings.security.twofa_code')}</label>
              <input
                className="input"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                inputMode="numeric"
                maxLength={6}
              />
            </div>
            <button className="btn-danger">{t('settings.security.twofa_disable')}</button>
            {twofaError && <p className="text-sm text-red-500">{twofaError}</p>}
          </form>
        )}
      </div>
    </div>
  )
}

function HouseholdTab() {
  const { t } = useTranslation()
  const user = useAuthStore((s) => s.user)
  const { data: households } = useHouseholds()
  const switchHousehold = useSwitchHousehold()
  const createHousehold = useCreateHousehold()
  const joinHousehold = useJoinHousehold()
  const activeId = user?.active_household_id ?? null
  const active = households?.find((h) => h.id === activeId)
  const isOwner = active?.role === 'owner'
  const { data: members } = useMembers(activeId)
  const changeRole = useChangeMemberRole(activeId)
  const removeMember = useRemoveMember(activeId)
  const { data: invites } = useInvites(activeId, isOwner)
  const createInvite = useCreateInvite(activeId)
  const deleteInvite = useDeleteInvite(activeId)

  const [newName, setNewName] = useState('')
  const [newCurrency, setNewCurrency] = useState('CHF')
  const [joinCode, setJoinCode] = useState('')
  const [inviteRole, setInviteRole] = useState<Role>('editor')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await createHousehold.mutateAsync({ name: newName, currency: newCurrency })
      setNewName('')
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    }
  }

  const join = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await joinHousehold.mutateAsync(joinCode.trim())
      setJoinCode('')
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    }
  }

  const copyInvite = async (code: string) => {
    await navigator.clipboard.writeText(`${window.location.origin}/join/${code}`)
    setMessage(t('common.copied'))
    setTimeout(() => setMessage(null), 1500)
  }

  return (
    <div className="space-y-8">
      <div>
        <h3 className="mb-3 font-semibold">{t('settings.household.switch')}</h3>
        <div className="space-y-2">
          {households?.map((h) => (
            <div
              key={h.id}
              className={`flex items-center gap-3 rounded-lg border p-3 ${
                h.id === activeId ? 'border-emerald-300 dark:border-emerald-800' : 'border-slate-200 dark:border-slate-800'
              }`}
            >
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">
                  {h.name} {h.id === activeId && '✓'}
                </p>
                <p className="text-xs text-slate-400">
                  {t(`settings.household.roles.${h.role}`)} · {h.currency} ·{' '}
                  {t('settings.household.member_count', { count: h.member_count })}
                </p>
              </div>
              {h.id !== activeId && (
                <button className="btn-secondary" onClick={() => switchHousehold.mutate(h.id)}>
                  {t('common.apply')}
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-6 sm:grid-cols-2">
        <form onSubmit={create} className="space-y-2">
          <h3 className="font-semibold">{t('settings.household.create_new')}</h3>
          <input
            className="input"
            placeholder={t('auth.household_name')}
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            required
          />
          <div className="flex gap-2">
            <input
              className="input w-24 uppercase"
              maxLength={3}
              value={newCurrency}
              onChange={(e) => setNewCurrency(e.target.value.toUpperCase())}
            />
            <button className="btn-secondary flex-1">{t('common.create')}</button>
          </div>
        </form>
        <form onSubmit={join} className="space-y-2">
          <h3 className="font-semibold">{t('settings.household.join')}</h3>
          <input
            className="input"
            placeholder={t('settings.household.join_code')}
            value={joinCode}
            onChange={(e) => setJoinCode(e.target.value)}
            required
          />
          <button className="btn-secondary w-full">{t('settings.household.join')}</button>
        </form>
      </div>
      {error && <p className="text-sm text-red-500">{error}</p>}

      <div>
        <h3 className="mb-3 font-semibold">{t('settings.household.members')}</h3>
        <div className="space-y-2">
          {members?.map((m) => (
            <div key={m.id} className="flex items-center gap-3 rounded-lg border border-slate-200 p-3 dark:border-slate-800">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{m.name}</p>
                <p className="text-xs text-slate-400">{m.email}</p>
              </div>
              {isOwner ? (
                <>
                  <select
                    className="input w-28"
                    value={m.role}
                    onChange={(e) => changeRole.mutate({ userId: m.user_id, role: e.target.value })}
                  >
                    {(['owner', 'editor', 'viewer'] as const).map((r) => (
                      <option key={r} value={r}>
                        {t(`settings.household.roles.${r}`)}
                      </option>
                    ))}
                  </select>
                  {m.user_id !== user?.id && (
                    <button
                      className="btn-ghost text-red-500"
                      onClick={() => {
                        if (window.confirm(t('common.confirm_delete'))) removeMember.mutate(m.user_id)
                      }}
                    >
                      {t('settings.household.remove')}
                    </button>
                  )}
                </>
              ) : (
                <span className="badge bg-slate-100 dark:bg-slate-800">
                  {t(`settings.household.roles.${m.role}`)}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>

      {isOwner && (
        <div>
          <div className="mb-3 flex items-center gap-3">
            <h3 className="font-semibold">{t('settings.household.invites')}</h3>
            <select className="input w-28" value={inviteRole} onChange={(e) => setInviteRole(e.target.value as Role)}>
              {(['editor', 'viewer', 'owner'] as const).map((r) => (
                <option key={r} value={r}>
                  {t(`settings.household.roles.${r}`)}
                </option>
              ))}
            </select>
            <button className="btn-secondary" onClick={() => createInvite.mutate(inviteRole)}>
              {t('settings.household.create_invite')}
            </button>
            {message && <span className="text-sm text-emerald-600">{message}</span>}
          </div>
          <p className="mb-2 text-xs text-slate-400">{t('settings.household.invite_hint')}</p>
          <div className="space-y-2">
            {invites
              ?.filter((i) => !i.used)
              .map((invite) => (
                <div
                  key={invite.id}
                  className="flex items-center gap-3 rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-800"
                >
                  <code className="font-mono font-semibold">{invite.code}</code>
                  <span className="badge bg-slate-100 dark:bg-slate-800">
                    {t(`settings.household.roles.${invite.role}`)}
                  </span>
                  <span className="text-xs text-slate-400">
                    {t('settings.household.expires', { date: fmtDate(invite.expires_at.slice(0, 10)) })}
                  </span>
                  <div className="flex-1" />
                  <button className="btn-ghost" onClick={() => void copyInvite(invite.code)}>
                    📋
                  </button>
                  <button className="btn-ghost text-red-500" onClick={() => deleteInvite.mutate(invite.id)}>
                    ✕
                  </button>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}

function TokensTab() {
  const { t } = useTranslation()
  const { data: tokens } = useApiTokens()
  const createToken = useCreateApiToken()
  const deleteToken = useDeleteApiToken()
  const [modalOpen, setModalOpen] = useState(false)
  const [name, setName] = useState('')
  const [expiresDays, setExpiresDays] = useState('')
  const [created, setCreated] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const res = await createToken.mutateAsync({
      name,
      ...(expiresDays ? { expires_days: Number(expiresDays) } : {}),
    })
    setCreated(res.token)
    setName('')
    setExpiresDays('')
  }

  const copy = async () => {
    if (!created) return
    await navigator.clipboard.writeText(created)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-500">{t('settings.tokens.hint')}</p>
      <button className="btn-primary" onClick={() => { setModalOpen(true); setCreated(null) }}>
        {t('settings.tokens.new')}
      </button>
      <div className="space-y-2">
        {tokens?.map((token) => (
          <div key={token.id} className="flex items-center gap-3 rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-800">
            <div className="min-w-0 flex-1">
              <p className="font-medium">{token.name}</p>
              <p className="text-xs text-slate-400">
                <code>{token.prefix}…</code> ·{' '}
                {token.last_used_at
                  ? `${t('settings.tokens.last_used')}: ${fmtDateTime(token.last_used_at)}`
                  : t('settings.tokens.never_used')}
                {token.expires_at && ` · ${t('settings.tokens.expires')}: ${fmtDate(token.expires_at.slice(0, 10))}`}
              </p>
            </div>
            <button
              className="btn-ghost text-red-500"
              onClick={() => {
                if (window.confirm(t('common.confirm_delete'))) deleteToken.mutate(token.id)
              }}
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      <Modal open={modalOpen} onClose={() => setModalOpen(false)} title={t('settings.tokens.new')}>
        {created ? (
          <div className="space-y-3">
            <p className="text-sm">{t('settings.tokens.created')}</p>
            <div className="flex items-center gap-2">
              <code className="block flex-1 break-all rounded-lg bg-slate-100 p-3 text-xs dark:bg-slate-800">
                {created}
              </code>
              <button className="btn-secondary" onClick={() => void copy()}>
                {copied ? '✓' : '📋'}
              </button>
            </div>
            <div className="flex justify-end">
              <button className="btn-primary" onClick={() => setModalOpen(false)}>
                {t('common.done')}
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="label">{t('common.name')}</label>
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div>
              <label className="label">{t('settings.tokens.expires_days')}</label>
              <input
                type="number"
                min={1}
                className="input"
                value={expiresDays}
                onChange={(e) => setExpiresDays(e.target.value)}
              />
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" className="btn-secondary" onClick={() => setModalOpen(false)}>
                {t('common.cancel')}
              </button>
              <button className="btn-primary" disabled={createToken.isPending}>
                {t('common.create')}
              </button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  )
}

function RatesTab() {
  const { t } = useTranslation()
  const { data: rates } = useRates()
  const saveRates = useSaveRates()
  const [edits, setEdits] = useState<Record<string, string>>({})
  const [newCurrency, setNewCurrency] = useState('')
  const [newRate, setNewRate] = useState('')

  const save = async () => {
    const payload = Object.entries(edits)
      .map(([currency, text]) => ({ currency, rate: Number(text.replace(',', '.')) }))
      .filter((r) => !Number.isNaN(r.rate) && r.rate > 0)
    if (newCurrency.trim() && newRate.trim()) {
      const rate = Number(newRate.replace(',', '.'))
      if (!Number.isNaN(rate) && rate > 0) payload.push({ currency: newCurrency.trim().toUpperCase(), rate })
    }
    if (payload.length > 0) await saveRates.mutateAsync(payload)
    setEdits({})
    setNewCurrency('')
    setNewRate('')
  }

  return (
    <div className="max-w-md space-y-4">
      <p className="text-sm text-slate-500">
        {t('settings.rates.hint', { base: rates?.base_currency ?? 'CHF' })}
      </p>
      <div className="space-y-2">
        {rates?.rates.map((r) => (
          <div key={r.currency} className="flex items-center gap-3">
            <span className="w-16 font-mono text-sm font-semibold">{r.currency}</span>
            <input
              className="input"
              inputMode="decimal"
              value={edits[r.currency] ?? String(r.rate)}
              disabled={r.currency === rates.base_currency}
              onChange={(e) => setEdits((prev) => ({ ...prev, [r.currency]: e.target.value }))}
            />
          </div>
        ))}
        <div className="flex items-center gap-3">
          <input
            className="input w-16 uppercase"
            maxLength={3}
            placeholder="EUR"
            value={newCurrency}
            onChange={(e) => setNewCurrency(e.target.value.toUpperCase())}
          />
          <input
            className="input"
            inputMode="decimal"
            placeholder={t('settings.rates.rate')}
            value={newRate}
            onChange={(e) => setNewRate(e.target.value)}
          />
        </div>
      </div>
      <button className="btn-primary" onClick={() => void save()} disabled={saveRates.isPending}>
        {t('common.save')}
      </button>
    </div>
  )
}

function SmtpTab() {
  const { t } = useTranslation()
  const user = useAuthStore((s) => s.user)
  const { data: smtp } = useSmtp(Boolean(user?.is_admin))
  const saveSmtp = useSaveSmtp()
  const testSmtp = useTestSmtp()
  const [host, setHost] = useState<string | null>(null)
  const [port, setPort] = useState<string | null>(null)
  const [username, setUsername] = useState<string | null>(null)
  const [password, setPassword] = useState('')
  const [fromEmail, setFromEmail] = useState<string | null>(null)
  const [useTls, setUseTls] = useState<boolean | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  if (!user?.is_admin) return <p className="text-sm text-slate-500">{t('settings.smtp.not_admin')}</p>

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    setMessage(null)
    await saveSmtp.mutateAsync({
      host: host ?? smtp?.host ?? '',
      port: Number(port ?? smtp?.port ?? 587),
      username: username ?? smtp?.username ?? '',
      from_email: fromEmail ?? smtp?.from_email ?? '',
      use_tls: useTls ?? smtp?.use_tls ?? true,
      ...(password ? { password } : {}),
    })
    setPassword('')
    setMessage(t('settings.profile.saved'))
  }

  const test = async () => {
    setMessage(null)
    try {
      const res = await testSmtp.mutateAsync(undefined)
      setMessage(res.sent ? t('settings.smtp.test_sent', { to: res.to }) : t('settings.smtp.test_failed'))
    } catch {
      setMessage(t('settings.smtp.test_failed'))
    }
  }

  return (
    <form onSubmit={save} className="max-w-md space-y-4">
      <p className="text-sm text-slate-500">{t('settings.smtp.hint')}</p>
      <div className="grid grid-cols-3 gap-3">
        <div className="col-span-2">
          <label className="label">{t('settings.smtp.host')}</label>
          <input className="input" value={host ?? smtp?.host ?? ''} onChange={(e) => setHost(e.target.value)} />
        </div>
        <div>
          <label className="label">{t('settings.smtp.port')}</label>
          <input
            type="number"
            className="input"
            value={port ?? String(smtp?.port ?? 587)}
            onChange={(e) => setPort(e.target.value)}
          />
        </div>
      </div>
      <div>
        <label className="label">{t('settings.smtp.username')}</label>
        <input className="input" value={username ?? smtp?.username ?? ''} onChange={(e) => setUsername(e.target.value)} />
      </div>
      <div>
        <label className="label">
          {t('settings.smtp.password')} ({smtp?.has_password ? t('settings.smtp.password_keep') : ''})
        </label>
        <input type="password" className="input" value={password} onChange={(e) => setPassword(e.target.value)} />
      </div>
      <div>
        <label className="label">{t('settings.smtp.from')}</label>
        <input className="input" value={fromEmail ?? smtp?.from_email ?? ''} onChange={(e) => setFromEmail(e.target.value)} />
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={useTls ?? smtp?.use_tls ?? true}
          onChange={(e) => setUseTls(e.target.checked)}
        />
        {t('settings.smtp.tls')}
      </label>
      {message && <p className="text-sm text-emerald-600">{message}</p>}
      <div className="flex gap-2">
        <button className="btn-primary" disabled={saveSmtp.isPending}>
          {t('common.save')}
        </button>
        <button type="button" className="btn-secondary" onClick={() => void test()} disabled={testSmtp.isPending}>
          {t('settings.smtp.test')}
        </button>
      </div>
    </form>
  )
}

export function SettingsPage() {
  const { t } = useTranslation()
  const user = useAuthStore((s) => s.user)
  const [tab, setTab] = useState<Tab>('profile')

  const tabs: Tab[] = ['profile', 'security', 'household', 'tokens', 'rates', ...(user?.is_admin ? (['smtp'] as Tab[]) : [])]

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">{t('settings.title')}</h1>
      <div className="flex flex-wrap gap-1 border-b border-slate-200 dark:border-slate-800">
        {tabs.map((tb) => (
          <button
            key={tb}
            className={`border-b-2 px-3 py-2 text-sm font-medium ${
              tab === tb
                ? 'border-emerald-500 text-emerald-600 dark:text-emerald-400'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
            onClick={() => setTab(tb)}
          >
            {t(`settings.tabs.${tb}`)}
          </button>
        ))}
      </div>
      <div className="card p-5">
        {tab === 'profile' && <ProfileTab />}
        {tab === 'security' && <SecurityTab />}
        {tab === 'household' && <HouseholdTab />}
        {tab === 'tokens' && <TokensTab />}
        {tab === 'rates' && <RatesTab />}
        {tab === 'smtp' && <SmtpTab />}
      </div>
    </div>
  )
}
