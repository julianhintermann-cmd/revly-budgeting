import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'

import type { Category } from '@/lib/types'

interface CategorySelectProps {
  categories: Category[]
  value: string // category id as string, '' = none
  onChange: (value: string) => void
  typeFilter?: 'expense' | 'income' | 'all'
  allowNone?: boolean
  className?: string
  id?: string
}

/** Flat select with income/expense groups; children are indented under their parent. */
export function CategorySelect({
  categories,
  value,
  onChange,
  typeFilter = 'all',
  allowNone = true,
  className = 'input',
  id,
}: CategorySelectProps) {
  const { t } = useTranslation()

  const groups = useMemo(() => {
    const active = categories.filter((c) => !c.archived)
    const ordered = (type: 'income' | 'expense') => {
      const ofType = active.filter((c) => c.type === type)
      const roots = ofType.filter((c) => c.parent_id == null)
      const result: { cat: Category; depth: number }[] = []
      for (const root of roots) {
        result.push({ cat: root, depth: 0 })
        for (const child of ofType.filter((c) => c.parent_id === root.id)) {
          result.push({ cat: child, depth: 1 })
        }
      }
      return result
    }
    return {
      income: typeFilter !== 'expense' ? ordered('income') : [],
      expense: typeFilter !== 'income' ? ordered('expense') : [],
    }
  }, [categories, typeFilter])

  return (
    <select id={id} className={className} value={value} onChange={(e) => onChange(e.target.value)}>
      {allowNone && <option value="">{t('common.none')}</option>}
      {groups.expense.length > 0 && (
        <optgroup label={t('categories.expense_section')}>
          {groups.expense.map(({ cat, depth }) => (
            <option key={cat.id} value={String(cat.id)}>
              {depth > 0 ? ' ' : ''}
              {cat.icon} {cat.name}
            </option>
          ))}
        </optgroup>
      )}
      {groups.income.length > 0 && (
        <optgroup label={t('categories.income_section')}>
          {groups.income.map(({ cat, depth }) => (
            <option key={cat.id} value={String(cat.id)}>
              {depth > 0 ? ' ' : ''}
              {cat.icon} {cat.name}
            </option>
          ))}
        </optgroup>
      )}
    </select>
  )
}
