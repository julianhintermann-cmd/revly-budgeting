import { Pencil } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Modal } from '@/components/Modal'
import { Spinner } from '@/components/Spinner'
import { useCategories, useCreateCategory, useDeleteCategory, useUpdateCategory } from '@/hooks/queries'
import { ApiError } from '@/lib/api'
import type { Category, CategoryType } from '@/lib/types'

export function CategoriesPage() {
  const { t } = useTranslation()
  const { data: categories, isLoading } = useCategories()
  const createCategory = useCreateCategory()
  const updateCategory = useUpdateCategory()
  const deleteCategory = useDeleteCategory()

  const [showArchived, setShowArchived] = useState(false)
  const [formOpen, setFormOpen] = useState(false)
  const [editing, setEditing] = useState<Category | null>(null)
  const [formType, setFormType] = useState<CategoryType>('expense')
  const [name, setName] = useState('')
  const [icon, setIcon] = useState('📁')
  const [color, setColor] = useState('#10b981')
  const [parentId, setParentId] = useState('')
  const [rollover, setRollover] = useState(true)
  const [archived, setArchived] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const parents = useMemo(
    () => (categories ?? []).filter((c) => c.type === formType && c.parent_id == null && c.id !== editing?.id),
    [categories, formType, editing]
  )

  const openForm = (cat: Category | null, type: CategoryType) => {
    setEditing(cat)
    setFormType(cat?.type ?? type)
    setName(cat?.name ?? '')
    setIcon(cat?.icon ?? (type === 'income' ? '💰' : '📁'))
    setColor(cat?.color ?? '#10b981')
    setParentId(cat?.parent_id ? String(cat.parent_id) : '')
    setRollover(cat?.rollover ?? true)
    setArchived(cat?.archived ?? false)
    setError(null)
    setFormOpen(true)
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      if (editing) {
        await updateCategory.mutateAsync({
          id: editing.id,
          name,
          icon,
          color,
          rollover,
          archived,
          ...(parentId ? { parent_id: Number(parentId) } : { clear_parent: true }),
        })
      } else {
        await createCategory.mutateAsync({
          name,
          icon,
          color,
          type: formType,
          rollover,
          ...(parentId ? { parent_id: Number(parentId) } : {}),
        })
      }
      setFormOpen(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : t('common.error'))
    }
  }

  const remove = async () => {
    if (!editing || !window.confirm(t('common.confirm_delete'))) return
    try {
      await deleteCategory.mutateAsync(editing.id)
      setFormOpen(false)
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setError(t('categories.delete_blocked'))
      else setError(err instanceof Error ? err.message : t('common.error'))
    }
  }

  if (isLoading) return <Spinner />

  const section = (type: CategoryType) => {
    const ofType = (categories ?? []).filter(
      (c) => c.type === type && (showArchived || !c.archived)
    )
    const roots = ofType.filter((c) => c.parent_id == null)
    const rows: { cat: Category; depth: number }[] = []
    for (const root of roots) {
      rows.push({ cat: root, depth: 0 })
      for (const child of ofType.filter((c) => c.parent_id === root.id)) rows.push({ cat: child, depth: 1 })
    }
    return (
      <div className="card p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">
            {type === 'income' ? t('categories.income_section') : t('categories.expense_section')}
          </h2>
          <button className="btn-secondary" onClick={() => openForm(null, type)}>
            {t('categories.new')}
          </button>
        </div>
        <ul className="divide-y divide-slate-100 dark:divide-slate-800">
          {rows.map(({ cat, depth }) => (
            <li
              key={cat.id}
              className={`flex items-center gap-2 py-2 ${depth > 0 ? 'pl-6' : ''} ${cat.archived ? 'opacity-50' : ''}`}
            >
              <span className="flex h-7 w-7 items-center justify-center rounded-lg text-base" style={{ background: `${cat.color}22` }}>
                {cat.icon}
              </span>
              <span className="text-sm font-medium">{cat.name}</span>
              {type === 'expense' && !cat.rollover && (
                <span className="badge bg-slate-100 text-slate-500 dark:bg-slate-800">
                  {t('budget.rollover_off')}
                </span>
              )}
              {cat.archived && (
                <span className="badge bg-slate-100 text-slate-400 dark:bg-slate-800">{t('common.archived')}</span>
              )}
              <button className="btn-ghost ml-auto" onClick={() => openForm(cat, type)}>
                <Pencil className="h-4 w-4" />
              </button>
            </li>
          ))}
        </ul>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-bold">{t('categories.title')}</h1>
        <div className="flex-1" />
        <label className="flex items-center gap-2 text-sm text-slate-500">
          <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
          {t('common.show_archived')}
        </label>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {section('expense')}
        {section('income')}
      </div>

      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editing ? t('categories.edit') : t('categories.new')}
      >
        <form onSubmit={submit} className="space-y-4">
          <div className="grid grid-cols-4 gap-3">
            <div className="col-span-2">
              <label className="label">{t('common.name')}</label>
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div>
              <label className="label">{t('categories.icon')}</label>
              <input className="input text-center" maxLength={4} value={icon} onChange={(e) => setIcon(e.target.value)} />
            </div>
            <div>
              <label className="label">{t('categories.color')}</label>
              <input
                type="color"
                className="input h-9 cursor-pointer p-1"
                value={color}
                onChange={(e) => setColor(e.target.value)}
              />
            </div>
          </div>
          {formType === 'expense' && (
            <div>
              <label className="label">
                {t('categories.parent')} ({t('common.optional')})
              </label>
              <select className="input" value={parentId} onChange={(e) => setParentId(e.target.value)}>
                <option value="">{t('common.none')}</option>
                {parents.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.icon} {p.name}
                  </option>
                ))}
              </select>
            </div>
          )}
          {formType === 'expense' && (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={rollover} onChange={(e) => setRollover(e.target.checked)} />
              {t('categories.rollover')}
            </label>
          )}
          {editing && (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={archived} onChange={(e) => setArchived(e.target.checked)} />
              {t('common.archive')}
            </label>
          )}
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="flex justify-between">
            {editing ? (
              <button type="button" className="btn-danger" onClick={remove}>
                {t('common.delete')}
              </button>
            ) : (
              <span />
            )}
            <div className="flex gap-2">
              <button type="button" className="btn-secondary" onClick={() => setFormOpen(false)}>
                {t('common.cancel')}
              </button>
              <button className="btn-primary" disabled={createCategory.isPending || updateCategory.isPending}>
                {t('common.save')}
              </button>
            </div>
          </div>
        </form>
      </Modal>
    </div>
  )
}
