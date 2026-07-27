import type { ReactNode } from 'react'

export function EmptyState({ text, action }: { text: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 py-10 text-center text-sm text-slate-500 dark:text-slate-400">
      <span className="text-3xl">🍃</span>
      <p>{text}</p>
      {action}
    </div>
  )
}
