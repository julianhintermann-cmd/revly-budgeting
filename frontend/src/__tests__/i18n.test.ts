import { describe, expect, it } from 'vitest'

import de from '@/i18n/de.json'
import en from '@/i18n/en.json'

function flattenKeys(obj: Record<string, unknown>, prefix = ''): string[] {
  const out: string[] = []
  for (const [key, value] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${key}` : key
    if (value !== null && typeof value === 'object') {
      out.push(...flattenKeys(value as Record<string, unknown>, path))
    } else {
      out.push(path)
    }
  }
  return out
}

describe('i18n resources', () => {
  it('German and English cover exactly the same keys', () => {
    expect(flattenKeys(en).sort()).toEqual(flattenKeys(de).sort())
  })

  it('has no empty translations', () => {
    for (const resources of [de, en]) {
      for (const key of flattenKeys(resources)) {
        const value = key.split('.').reduce<unknown>((acc, part) => (acc as Record<string, unknown>)[part], resources)
        expect(String(value).length, key).toBeGreaterThan(0)
      }
    }
  })
})
