import clsx from 'clsx'

import { fmtMoney } from '@/lib/format'

interface MoneyProps {
  cents: number
  currency?: string
  colored?: boolean
  className?: string
}

export function Money({ cents, currency = 'CHF', colored = false, className }: MoneyProps) {
  return (
    <span
      className={clsx(
        'tabular-nums',
        colored && cents > 0 && 'text-emerald-600 dark:text-emerald-400',
        colored && cents < 0 && 'text-red-600 dark:text-red-400',
        className
      )}
    >
      {fmtMoney(cents, currency)}
    </span>
  )
}
