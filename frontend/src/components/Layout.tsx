import {
  ArrowLeftRight,
  BarChart3,
  CalendarClock,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  PiggyBank,
  Plus,
  Settings,
  Shapes,
  Sun,
  Target,
  TrendingDown,
  Upload,
  Wallet,
} from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { NotificationBell } from '@/components/NotificationBell'
import { ShortcutsHelp } from '@/components/ShortcutsHelp'
import { TransactionFormModal } from '@/components/TransactionForm'
import { useHouseholds, useSwitchHousehold } from '@/hooks/queries'
import { useShortcuts } from '@/hooks/useShortcuts'
import { setLocale } from '@/i18n'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'
import { useUiStore } from '@/stores/ui'

const NAV = [
  { to: '/', key: 'dashboard', icon: LayoutDashboard, end: true },
  { to: '/accounts', key: 'accounts', icon: Wallet },
  { to: '/transactions', key: 'transactions', icon: ArrowLeftRight },
  { to: '/budget', key: 'budget', icon: PiggyBank },
  { to: '/categories', key: 'categories', icon: Shapes },
  { to: '/recurring', key: 'recurring', icon: CalendarClock },
  { to: '/goals', key: 'goals', icon: Target },
  { to: '/debts', key: 'debts', icon: TrendingDown },
  { to: '/reports', key: 'reports', icon: BarChart3 },
  { to: '/import', key: 'import', icon: Upload },
  { to: '/settings', key: 'settings', icon: Settings },
] as const

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useTranslation()
  return (
    <>
      <div className="flex items-center gap-2 px-4 py-5">
        <img src="/favicon.svg" alt="" className="h-8 w-8" />
        <span className="text-lg font-bold tracking-tight">revly</span>
      </div>
      <nav className="flex-1 space-y-0.5 px-2">
        {NAV.map(({ to, key, icon: Icon, ...rest }) => (
          <NavLink
            key={to}
            to={to}
            end={'end' in rest}
            onClick={onNavigate}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-emerald-600/10 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400'
                  : 'text-slate-600 hover:bg-slate-200/60 dark:text-slate-300 dark:hover:bg-slate-800'
              }`
            }
          >
            <Icon className="h-4 w-4" />
            {t(`nav.${key}`)}
          </NavLink>
        ))}
      </nav>
    </>
  )
}

export function Layout() {
  useShortcuts()
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const clear = useAuthStore((s) => s.clear)
  const theme = useUiStore((s) => s.theme)
  const toggleTheme = useUiStore((s) => s.toggleTheme)
  const openTxnModal = useUiStore((s) => s.openTxnModal)
  const [mobileNav, setMobileNav] = useState(false)
  const [search, setSearch] = useState('')
  const { data: households } = useHouseholds()
  const switchHousehold = useSwitchHousehold()

  const logout = async () => {
    const refreshToken = useAuthStore.getState().refreshToken
    try {
      if (refreshToken) await api('/auth/logout', { method: 'POST', body: { refresh_token: refreshToken } })
    } catch {
      /* token may already be gone */
    }
    clear()
    navigate('/login')
  }

  const toggleLocale = () => {
    const next = i18n.language === 'de' ? 'en' : 'de'
    setLocale(next)
  }

  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-56 flex-col border-r border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900 md:flex">
        <SidebarContent />
      </aside>

      {mobileNav && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div className="absolute inset-0 bg-slate-950/50" onClick={() => setMobileNav(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-64 flex-col bg-white dark:bg-slate-900">
            <SidebarContent onNavigate={() => setMobileNav(false)} />
          </aside>
        </div>
      )}

      <div className="md:pl-56">
        <header className="sticky top-0 z-10 flex items-center gap-2 border-b border-slate-200 bg-white/80 px-4 py-2.5 backdrop-blur dark:border-slate-800 dark:bg-slate-950/80">
          <button className="btn-ghost md:hidden" onClick={() => setMobileNav(true)} aria-label="menu">
            <Menu className="h-5 w-5" />
          </button>
          <input
            id="global-search"
            className="input hidden w-56 md:block"
            placeholder={t('common.search')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                navigate(`/transactions?q=${encodeURIComponent(search)}`)
                setSearch('')
              }
            }}
          />
          <div className="flex-1" />
          <button className="btn-primary" onClick={() => openTxnModal()}>
            <Plus className="h-4 w-4" />
            <span className="hidden sm:inline">{t('transactions.new')}</span>
          </button>
          {households && households.length > 1 && (
            <select
              className="input hidden w-40 sm:block"
              value={user?.active_household_id ?? ''}
              onChange={(e) => switchHousehold.mutate(Number(e.target.value))}
            >
              {households.map((h) => (
                <option key={h.id} value={h.id}>
                  {h.name}
                </option>
              ))}
            </select>
          )}
          <NotificationBell />
          <button className="btn-ghost" onClick={toggleTheme} aria-label="theme">
            {theme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
          </button>
          <button className="btn-ghost text-xs font-bold" onClick={toggleLocale} aria-label="language">
            {i18n.language === 'de' ? 'EN' : 'DE'}
          </button>
          <button className="btn-ghost" onClick={logout} title={t('nav.logout')} aria-label={t('nav.logout')}>
            <LogOut className="h-5 w-5" />
          </button>
        </header>

        <main className="mx-auto max-w-6xl px-4 py-6 pb-20">
          <Outlet />
        </main>
      </div>

      <TransactionFormModal />
      <ShortcutsHelp />
    </div>
  )
}
