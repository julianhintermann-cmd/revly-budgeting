import { Navigate, Outlet, Route, Routes } from 'react-router-dom'

import { Layout } from '@/components/Layout'
import { Spinner } from '@/components/Spinner'
import { AccountsPage } from '@/pages/AccountsPage'
import { BudgetPage } from '@/pages/BudgetPage'
import { CategoriesPage } from '@/pages/CategoriesPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { DebtsPage } from '@/pages/DebtsPage'
import { GoalsPage } from '@/pages/GoalsPage'
import { ImportPage } from '@/pages/ImportPage'
import { LoginPage } from '@/pages/LoginPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { OnboardingPage } from '@/pages/OnboardingPage'
import { RecurringPage } from '@/pages/RecurringPage'
import { RegisterPage } from '@/pages/RegisterPage'
import { ReportsPage } from '@/pages/ReportsPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { TransactionsPage } from '@/pages/TransactionsPage'
import { useAuthStore } from '@/stores/auth'

function RequireAuth() {
  const status = useAuthStore((s) => s.status)
  if (status === 'loading')
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner />
      </div>
    )
  if (status !== 'authed') return <Navigate to="/login" replace />
  return <Outlet />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/join/:code" element={<RegisterPage />} />
      <Route element={<RequireAuth />}>
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route element={<Layout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/accounts" element={<AccountsPage />} />
          <Route path="/transactions" element={<TransactionsPage />} />
          <Route path="/budget" element={<BudgetPage />} />
          <Route path="/categories" element={<CategoriesPage />} />
          <Route path="/recurring" element={<RecurringPage />} />
          <Route path="/goals" element={<GoalsPage />} />
          <Route path="/debts" element={<DebtsPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/import" element={<ImportPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
