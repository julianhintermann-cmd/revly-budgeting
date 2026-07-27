import clsx from 'clsx'

interface ProgressBarProps {
  value: number // 0..100
  danger?: boolean
  className?: string
}

export function ProgressBar({ value, danger = false, className }: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, value))
  return (
    <div className={clsx('h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800', className)}>
      <div
        className={clsx(
          'h-full rounded-full transition-all',
          danger ? 'bg-red-500' : 'bg-emerald-500'
        )}
        style={{ width: `${clamped}%` }}
      />
    </div>
  )
}
