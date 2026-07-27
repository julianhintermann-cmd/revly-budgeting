import type { TooltipProps } from 'recharts'

import { fmtMoney } from '@/lib/format'

interface ChartTooltipProps extends TooltipProps<number, string> {
  currency?: string
  labelFormatter?: (label: unknown) => string
}

/** Shared money tooltip: ink-colored text, series identity via color dot. */
export function ChartTooltip({ active, payload, label, currency = 'CHF', labelFormatter }: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) return null
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-md dark:border-slate-700 dark:bg-slate-900">
      <p className="mb-1 font-semibold text-slate-700 dark:text-slate-200">
        {labelFormatter ? labelFormatter(label) : String(label ?? '')}
      </p>
      <div className="space-y-0.5">
        {payload.map((entry) => (
          <div key={String(entry.dataKey)} className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full" style={{ background: entry.color }} />
            <span className="text-slate-500 dark:text-slate-400">{entry.name}</span>
            <span className="ml-auto pl-4 tabular-nums text-slate-700 dark:text-slate-200">
              {fmtMoney(Number(entry.value ?? 0), currency)}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
