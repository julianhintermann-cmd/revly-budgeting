import { describe, expect, it } from 'vitest'

import { centsToInput, monthAdd, parseAmountInput } from '@/lib/format'

describe('parseAmountInput', () => {
  it('parses plain decimals', () => {
    expect(parseAmountInput('12.50')).toBe(1250)
    expect(parseAmountInput('0.05')).toBe(5)
    expect(parseAmountInput('100')).toBe(10000)
  })
  it('parses comma decimals', () => {
    expect(parseAmountInput('12,50')).toBe(1250)
    expect(parseAmountInput('1.234,56')).toBe(123456)
  })
  it('parses swiss thousand separators', () => {
    expect(parseAmountInput("1'250.00")).toBe(125000)
    expect(parseAmountInput('1,234.56')).toBe(123456)
  })
  it('rejects garbage', () => {
    expect(parseAmountInput('abc')).toBeNull()
    expect(parseAmountInput('')).toBeNull()
  })
})

describe('monthAdd', () => {
  it('adds and subtracts across year boundaries', () => {
    expect(monthAdd('2026-01', 1)).toBe('2026-02')
    expect(monthAdd('2026-12', 1)).toBe('2027-01')
    expect(monthAdd('2026-01', -1)).toBe('2025-12')
    expect(monthAdd('2026-06', -7)).toBe('2025-11')
  })
})

describe('centsToInput', () => {
  it('renders absolute two-decimal strings', () => {
    expect(centsToInput(1250)).toBe('12.50')
    expect(centsToInput(-1250)).toBe('12.50')
    expect(centsToInput(0)).toBe('0.00')
  })
})
