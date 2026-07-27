import { useTranslation } from 'react-i18next'

import { Modal } from '@/components/Modal'
import { useUiStore } from '@/stores/ui'

const SHORTCUTS: { keys: string; labelKey: string }[] = [
  { keys: 'n', labelKey: 'shortcuts.new_transaction' },
  { keys: 'g d', labelKey: 'shortcuts.goto_dashboard' },
  { keys: 'g t', labelKey: 'shortcuts.goto_transactions' },
  { keys: 'g b', labelKey: 'shortcuts.goto_budget' },
  { keys: '/', labelKey: 'shortcuts.search' },
  { keys: '?', labelKey: 'shortcuts.help' },
]

export function ShortcutsHelp() {
  const { t } = useTranslation()
  const open = useUiStore((s) => s.shortcutsOpen)
  const setOpen = useUiStore((s) => s.setShortcutsOpen)

  return (
    <Modal open={open} onClose={() => setOpen(false)} title={t('shortcuts.title')}>
      <ul className="space-y-2">
        {SHORTCUTS.map((s) => (
          <li key={s.keys} className="flex items-center justify-between text-sm">
            <span>{t(s.labelKey)}</span>
            <span className="flex gap-1">
              {s.keys.split(' ').map((k) => (
                <kbd
                  key={k}
                  className="rounded border border-slate-300 bg-slate-100 px-2 py-0.5 font-mono text-xs dark:border-slate-600 dark:bg-slate-800"
                >
                  {k}
                </kbd>
              ))}
            </span>
          </li>
        ))}
      </ul>
    </Modal>
  )
}
