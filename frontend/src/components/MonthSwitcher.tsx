import { ChevronLeft, ChevronRight } from 'lucide-react'

import { fmtMonth, monthAdd } from '@/lib/format'

interface MonthSwitcherProps {
  month: string
  onChange: (month: string) => void
}

export function MonthSwitcher({ month, onChange }: MonthSwitcherProps) {
  return (
    <div className="flex items-center gap-1">
      <button className="btn-ghost" onClick={() => onChange(monthAdd(month, -1))} aria-label="previous month">
        <ChevronLeft className="h-4 w-4" />
      </button>
      <span className="min-w-36 text-center text-sm font-semibold capitalize">{fmtMonth(month)}</span>
      <button className="btn-ghost" onClick={() => onChange(monthAdd(month, 1))} aria-label="next month">
        <ChevronRight className="h-4 w-4" />
      </button>
    </div>
  )
}
