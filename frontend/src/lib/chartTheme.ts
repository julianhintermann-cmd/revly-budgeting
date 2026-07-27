import { useUiStore } from '@/stores/ui'

/**
 * Chart colors validated with the dataviz palette validator against the actual
 * chart surfaces (light: #ffffff cards, dark: #0f172a cards). Slots are
 * semantic and entity-stable across every chart:
 *   1 income / assets, 2 expenses / liabilities, 3 net / balance, 4 reserve.
 */
export interface ChartTheme {
  series: [string, string, string, string]
  income: string
  expense: string
  net: string
  grid: string
  axisText: string
  tooltipBg: string
  tooltipBorder: string
  tooltipText: string
}

const LIGHT: ChartTheme = {
  series: ['#059669', '#ea580c', '#2563eb', '#db2777'],
  income: '#059669',
  expense: '#ea580c',
  net: '#2563eb',
  grid: '#e2e8f0',
  axisText: '#64748b',
  tooltipBg: '#ffffff',
  tooltipBorder: '#e2e8f0',
  tooltipText: '#0f172a',
}

const DARK: ChartTheme = {
  series: ['#059669', '#ea580c', '#3b82f6', '#ec4899'],
  income: '#059669',
  expense: '#ea580c',
  net: '#3b82f6',
  grid: '#1e293b',
  axisText: '#94a3b8',
  tooltipBg: '#0f172a',
  tooltipBorder: '#334155',
  tooltipText: '#f1f5f9',
}

export function useChartTheme(): ChartTheme {
  return useUiStore((s) => s.theme) === 'dark' ? DARK : LIGHT
}
