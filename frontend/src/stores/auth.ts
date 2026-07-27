import { create } from 'zustand'

import type { TokenPair, User } from '@/lib/types'

interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  status: 'loading' | 'authed' | 'anon'
  setAuth: (pair: TokenPair) => void
  setUser: (user: User) => void
  clear: () => void
  init: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  accessToken: typeof localStorage !== 'undefined' ? localStorage.getItem('revly-access') : null,
  refreshToken: typeof localStorage !== 'undefined' ? localStorage.getItem('revly-refresh') : null,
  status: 'loading',

  setAuth: (pair) => {
    localStorage.setItem('revly-access', pair.access_token)
    localStorage.setItem('revly-refresh', pair.refresh_token)
    set({
      user: pair.user,
      accessToken: pair.access_token,
      refreshToken: pair.refresh_token,
      status: 'authed',
    })
  },

  setUser: (user) => set({ user }),

  clear: () => {
    localStorage.removeItem('revly-access')
    localStorage.removeItem('revly-refresh')
    set({ user: null, accessToken: null, refreshToken: null, status: 'anon' })
  },

  init: async () => {
    if (!get().accessToken && !get().refreshToken) {
      set({ status: 'anon' })
      return
    }
    try {
      const { api } = await import('@/lib/api')
      const user = await api<User>('/users/me')
      set({ user, status: 'authed' })
    } catch {
      get().clear()
    }
  },
}))
