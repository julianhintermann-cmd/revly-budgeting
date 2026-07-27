import { Download } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { ChartTooltip } from '@/components/ChartTooltip'
import { Money } from '@/components/Money'
import { MonthSwitcher } from '@/components/MonthSwitcher'
import { Spinner } from '@/components/Spinner'
import {
  useCashflowCalendar,
  useHouseholds,
  useMoneyFlow,
  useNetWorth,
  useSpending,
  useTrend,
} from '@/hooks/queries'
import { downloadFile } from '@/lib/api'
import { useChartTheme } from '@/lib/chartTheme'
import { currentMonth, fmtMoney, fmtMonth, fmtMonthShort } from '@/lib/format'
import type { FlowRow, SpendingRow } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'

function monthBounds(month: string): { from: string; to: string } {
  const y = Number(month.slice(0, 4))
  const m = Number(month.slice(5, 7))
  const last = new Date(y, m, 0).getDate()
  return { from: `${month}-01`, to: `${month}-${String(last).padStart(2, '0')}` }
}

function HBarList({ rows, total, currency }: { rows: (SpendingRow | FlowRow)[]; total: number; currency: string }) {
  const max = rows.length > 0 ? rows[0].amount : 0
  return (
    <ul className="space-y-2">
      {rows.slice(0, 12).map((row) => (
        <li key={`${row.name}`} title={fmtMoney(row.amount, currency)}>
          <div className="mb-0.5 flex items-center justify-between text-sm">
            <span className="truncate">
              {row.icon} {row.name}
            </span>
            <span className="tabular-nums text-slate-500">{fmtMoney(row.amount, currency)}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
            <div
              className="h-full rounded-full"
              style={{ width: `${max > 0 ? (row.amount / max) * 100 : 0}%`, background: row.color }}
            />
          </div>
        </li>
      ))}
      {rows.length === 0 && <li className="py-4 text-center text-sm text-slate-400">–</li>}
      {total > 0 && rows.length > 0 && (
        <li className="border-t border-slate-100 pt-2 text-right text-sm font-semibold dark:border-slate-800">
          {fmtMoney(total, currency)}
        </li>
      )}
    </ul>
  )
}

export function ReportsPage() {
  const { t } = useTranslation()
  const chart = useChartTheme()
  const user = useAuthStore((s) => s.user)
  const [month, setMonth] = useState(currentMonth())
  const [trendMonths, setTrendMonths] = useState(12)
  const { from, to } = monthBounds(month)

  const { data: spending, isLoading } = useSpending(from, to)
  const { data: trend } = useTrend(trendMonths)
  const { data: netWorth } = useNetWorth(24)
  const { data: flow } = useMoneyFlow(month)
  const { data: calendar } = useCashflowCalendar(month)
  const { data: households } = useHouseholds()
  const currency = households?.find((h) => h.id === user?.active_household_id)?.currency ?? 'CHF'

  const moneyTick = (v: number | string) => {
    const value = Number(v) / 100
    if (Math.abs(value) >= 1000) return `${Math.round(value / 100) / 10}k`
    return String(Math.round(value))
  }

  const netWorthData = (netWorth ?? []).map((row) => ({
    month: row.month,
    assets: row.assets,
    liabilities: Math.abs(row.liabilities),
    net: row.net,
  }))

  if (isLoading) return <Spinner />

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-bold">{t('reports.title')}</h1>
        <MonthSwitcher month={month} onChange={setMonth} />
        <div className="flex-1" />
        <button
          className="btn-secondary"
          onClick={() => void downloadFile('/reports/export.csv', 'revly-transactions.csv', { date_from: from, date_to: to })}
        >
          <Download className="h-4 w-4" /> {t('reports.export_csv')}
        </button>
        <button
          className="btn-secondary"
          onClick={() => void downloadFile('/reports/export.pdf', `revly-report-${month}.pdf`, { month })}
        >
          <Download className="h-4 w-4" /> {t('reports.export_pdf')}
        </button>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card p-4">
          <h2 className="mb-3 text-sm font-semibold">
            {t('reports.spending')} – {fmtMonth(month)}
          </h2>
          <HBarList rows={spending?.rows ?? []} total={spending?.total ?? 0} currency={currency} />
        </div>

        <div className="card p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold">{t('reports.trend')}</h2>
            <select
              className="input w-32 py-1 text-xs"
              value={trendMonths}
              onChange={(e) => setTrendMonths(Number(e.target.value))}
            >
              <option value={12}>{t('reports.months_12')}</option>
              <option value={24}>{t('reports.months_24')}</option>
            </select>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={trend ?? []} margin={{ top: 4, right: 8, bottom: 0, left: 0 }} barGap={2}>
                <CartesianGrid stroke={chart.grid} vertical={false} />
                <XAxis
                  dataKey="month"
                  tickFormatter={(m) => fmtMonthShort(String(m))}
                  tick={{ fill: chart.axisText, fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  minTickGap={20}
                />
                <YAxis
                  tickFormatter={moneyTick}
                  tick={{ fill: chart.axisText, fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  width={44}
                />
                <Tooltip content={<ChartTooltip currency={currency} labelFormatter={(l) => fmtMonth(String(l))} />} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="income" name={t('dashboard.income')} fill={chart.income} radius={[4, 4, 0, 0]} maxBarSize={18} />
                <Bar dataKey="expenses" name={t('dashboard.expenses')} fill={chart.expense} radius={[4, 4, 0, 0]} maxBarSize={18} />
                <Line type="monotone" dataKey="net" name={t('reports.net')} stroke={chart.net} strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-4">
          <h2 className="mb-3 text-sm font-semibold">{t('reports.net_worth')}</h2>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={netWorthData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }} barGap={2}>
                <CartesianGrid stroke={chart.grid} vertical={false} />
                <XAxis
                  dataKey="month"
                  tickFormatter={(m) => fmtMonthShort(String(m))}
                  tick={{ fill: chart.axisText, fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  minTickGap={20}
                />
                <YAxis
                  tickFormatter={moneyTick}
                  tick={{ fill: chart.axisText, fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                  width={44}
                />
                <Tooltip content={<ChartTooltip currency={currency} labelFormatter={(l) => fmtMonth(String(l))} />} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="assets" name={t('reports.assets')} fill={chart.income} radius={[4, 4, 0, 0]} maxBarSize={18} />
                <Bar dataKey="liabilities" name={t('reports.liabilities')} fill={chart.expense} radius={[4, 4, 0, 0]} maxBarSize={18} />
                <Line type="monotone" dataKey="net" name={t('reports.net')} stroke={chart.net} strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-4">
          <h2 className="mb-3 text-sm font-semibold">
            {t('reports.money_flow')} – {fmtMonth(month)}
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <p className="label">{t('reports.income_sources')}</p>
              <HBarList rows={flow?.income ?? []} total={flow?.income_total ?? 0} currency={currency} />
            </div>
            <div>
              <p className="label">{t('reports.expense_targets')}</p>
              <HBarList rows={flow?.expenses ?? []} total={flow?.expense_total ?? 0} currency={currency} />
            </div>
          </div>
        </div>

        <div className="card p-4 lg:col-span-2">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">
              {t('reports.cashflow')} – {fmtMonth(month)}
            </h2>
            <p className="text-xs text-slate-500">
              {t('reports.start_balance')}: <Money cents={calendar?.start_balance ?? 0} currency={currency} />
              {(calendar?.tight_days ?? 0) > 0 && (
                <span className="ml-3 text-red-600 dark:text-red-400">
                  ⚠️ {t('reports.tight_days', { count: calendar?.tight_days })}
                </span>
              )}
            </p>
          </div>
          <div className="grid grid-cols-7 gap-1">
            {(calendar?.days ?? []).map((day) => {
              const dayNum = Number(day.day.slice(8, 10))
              const negative = day.balance < 0
              const hasFlow = day.inflow > 0 || day.outflow > 0
              return (
                <div
                  key={day.day}
                  title={`${day.day}: +${fmtMoney(day.inflow, currency)} / -${fmtMoney(day.outflow, currency)} → ${fmtMoney(day.balance, currency)}`}
                  className={`rounded-lg border p-1.5 text-center ${
                    negative
                      ? 'border-red-200 bg-red-50 dark:border-red-900 dark:bg-red-950/30'
                      : hasFlow
                        ? 'border-slate-200 bg-slate-50 dark:border-slate-700 dark:bg-slate-800/50'
                        : 'border-slate-100 dark:border-slate-800'
                  }`}
                >
                  <p className="text-xs font-medium text-slate-500">{dayNum}</p>
                  {day.net !== 0 && (
                    <p
                      className={`truncate text-[10px] tabular-nums ${
                        day.net > 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400'
                      }`}
                    >
                      {day.net > 0 ? '+' : ''}
                      {Math.round(day.net / 100)}
                    </p>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}
