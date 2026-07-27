import { Bell } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { useMarkRead, useNotifications } from '@/hooks/queries'
import { fmtDateTime } from '@/lib/format'

const TYPE_ICONS: Record<string, string> = {
  bill_due: '📅',
  budget_overspent: '⚠️',
  goal_reached: '🎉',
  recurring_created: '🔁',
  member_joined: '👋',
  generic: '🔔',
}

export function NotificationBell() {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const { data } = useNotifications()
  const markRead = useMarkRead()
  const unread = data?.unread_count ?? 0

  return (
    <div className="relative">
      <button
        className="btn-ghost relative"
        onClick={() => setOpen((v) => !v)}
        aria-label={t('nav.notifications')}
      >
        <Bell className="h-5 w-5" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-40 mt-2 w-80 max-w-[90vw] overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-900">
            <div className="flex items-center justify-between border-b border-slate-200 px-3 py-2 dark:border-slate-800">
              <span className="text-sm font-semibold">{t('notifications.title')}</span>
              {unread > 0 && (
                <button
                  className="text-xs text-emerald-600 hover:underline dark:text-emerald-400"
                  onClick={() => markRead.mutate({ all: true })}
                >
                  {t('notifications.mark_all')}
                </button>
              )}
            </div>
            <div className="max-h-96 overflow-y-auto">
              {(data?.items.length ?? 0) === 0 && (
                <p className="p-4 text-center text-sm text-slate-500">{t('notifications.empty')}</p>
              )}
              {data?.items.map((n) => (
                <button
                  key={n.id}
                  className={`flex w-full gap-2 border-b border-slate-100 px-3 py-2 text-left last:border-0 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-800/50 ${
                    n.read ? 'opacity-60' : ''
                  }`}
                  onClick={() => {
                    if (!n.read) markRead.mutate({ ids: [n.id] })
                  }}
                >
                  <span className="mt-0.5 text-base">{TYPE_ICONS[n.type] ?? '🔔'}</span>
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium">{n.title}</span>
                    {n.body && (
                      <span className="block text-xs text-slate-500 dark:text-slate-400">{n.body}</span>
                    )}
                    <span className="block text-[11px] text-slate-400">{fmtDateTime(n.created_at)}</span>
                  </span>
                  {!n.read && <span className="ml-auto mt-1.5 h-2 w-2 shrink-0 rounded-full bg-emerald-500" />}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
