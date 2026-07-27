import i18n from '@/i18n'

function intlLocale(): string {
  return i18n.language === 'en' ? 'en-CH' : 'de-CH'
}

export function fmtMoney(cents: number, currency = 'CHF'): string {
  try {
    return new Intl.NumberFormat(intlLocale(), {
      style: 'currency',
      currency,
      currencyDisplay: 'code',
    }).format(cents / 100)
  } catch {
    return `${currency} ${(cents / 100).toFixed(2)}`
  }
}

export function fmtNumber(cents: number): string {
  return new Intl.NumberFormat(intlLocale(), {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(cents / 100)
}

export function fmtDate(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`)
  return new Intl.DateTimeFormat(intlLocale(), { day: '2-digit', month: '2-digit', year: 'numeric' }).format(d)
}

export function fmtDateTime(iso: string): string {
  return new Intl.DateTimeFormat(intlLocale(), {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(iso))
}

export function fmtMonth(month: string): string {
  const d = new Date(`${month}-01T00:00:00`)
  return new Intl.DateTimeFormat(intlLocale(), { month: 'long', year: 'numeric' }).format(d)
}

export function fmtMonthShort(month: string): string {
  const d = new Date(`${month}-01T00:00:00`)
  return new Intl.DateTimeFormat(intlLocale(), { month: 'short', year: '2-digit' }).format(d)
}

/** "12.50" / "12,50" / "1'250.00" -> cents; null on garbage */
export function parseAmountInput(raw: string): number | null {
  let s = raw.trim().replace(/['\s]/g, '')
  if (!s) return null
  if (s.includes(',') && s.includes('.')) {
    if (s.lastIndexOf(',') > s.lastIndexOf('.')) s = s.replace(/\./g, '').replace(',', '.')
    else s = s.replace(/,/g, '')
  } else {
    s = s.replace(',', '.')
  }
  const value = Number(s)
  if (Number.isNaN(value)) return null
  return Math.round(value * 100)
}

export function centsToInput(cents: number): string {
  return (Math.abs(cents) / 100).toFixed(2)
}

export function todayISO(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

export function currentMonth(): string {
  return todayISO().slice(0, 7)
}

export function monthAdd(month: string, delta: number): string {
  const y = Number(month.slice(0, 4))
  const m = Number(month.slice(5, 7))
  const idx = y * 12 + (m - 1) + delta
  const ny = Math.floor(idx / 12)
  const nm = (idx % 12) + 1
  return `${String(ny).padStart(4, '0')}-${String(nm).padStart(2, '0')}`
}
