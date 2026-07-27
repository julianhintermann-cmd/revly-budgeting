import { create } from 'zustand'

import type { Transaction } from '@/lib/types'

type Theme = 'light' | 'dark'

interface TxnModalState {
  open: boolean
  txn: Transaction | null
  defaultAccountId?: number
}

interface UiState {
  theme: Theme
  setTheme: (theme: Theme) => void
  toggleTheme: () => void
  sidebarOpen: boolean
  setSidebarOpen: (open: boolean) => void
  txnModal: TxnModalState
  openTxnModal: (txn?: Transaction | null, defaultAccountId?: number) => void
  closeTxnModal: () => void
  shortcutsOpen: boolean
  setShortcutsOpen: (open: boolean) => void
}

function initialTheme(): Theme {
  if (typeof document === 'undefined') return 'light'
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light'
}

export const useUiStore = create<UiState>((set, get) => ({
  theme: initialTheme(),
  setTheme: (theme) => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    localStorage.setItem('revly-theme', theme)
    set({ theme })
  },
  toggleTheme: () => get().setTheme(get().theme === 'dark' ? 'light' : 'dark'),
  sidebarOpen: false,
  setSidebarOpen: (sidebarOpen) => set({ sidebarOpen }),
  txnModal: { open: false, txn: null },
  openTxnModal: (txn = null, defaultAccountId) =>
    set({ txnModal: { open: true, txn, defaultAccountId } }),
  closeTxnModal: () => set({ txnModal: { open: false, txn: null } }),
  shortcutsOpen: false,
  setShortcutsOpen: (shortcutsOpen) => set({ shortcutsOpen }),
}))
