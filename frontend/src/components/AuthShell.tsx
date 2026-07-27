import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

export function AuthShell({ title, children }: { title: string; children: ReactNode }) {
  const { t } = useTranslation()
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-emerald-600/10 to-transparent px-4 dark:from-emerald-500/5">
      <div className="w-full max-w-md">
        <div className="mb-6 flex flex-col items-center gap-2">
          <img src="/favicon.svg" alt="" className="h-12 w-12" />
          <h1 className="text-2xl font-bold tracking-tight">{t('app.name')}</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">{t('app.tagline')}</p>
        </div>
        <div className="card p-6">
          <h2 className="mb-4 text-lg font-semibold">{title}</h2>
          {children}
        </div>
      </div>
    </div>
  )
}
