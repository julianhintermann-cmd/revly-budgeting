import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

import { useUiStore } from '@/stores/ui'

export function useShortcuts() {
  const navigate = useNavigate()
  const openTxnModal = useUiStore((s) => s.openTxnModal)
  const setShortcutsOpen = useUiStore((s) => s.setShortcutsOpen)
  const pendingG = useRef(false)

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.tagName === 'SELECT' ||
        target.isContentEditable
      )
        return
      if (e.metaKey || e.ctrlKey || e.altKey) return

      const key = e.key.toLowerCase()
      if (pendingG.current) {
        pendingG.current = false
        if (key === 'd') {
          e.preventDefault()
          navigate('/')
        } else if (key === 't') {
          e.preventDefault()
          navigate('/transactions')
        } else if (key === 'b') {
          e.preventDefault()
          navigate('/budget')
        }
        return
      }
      if (key === 'g') {
        pendingG.current = true
        window.setTimeout(() => {
          pendingG.current = false
        }, 800)
        return
      }
      if (key === 'n') {
        e.preventDefault()
        openTxnModal()
      } else if (key === '/') {
        e.preventDefault()
        document.getElementById('global-search')?.focus()
      } else if (e.key === '?') {
        e.preventDefault()
        setShortcutsOpen(true)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [navigate, openTxnModal, setShortcutsOpen])
}
