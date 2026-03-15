import { create } from 'zustand'
import { type User } from '@supabase/supabase-js'

interface AuthState {
  user: User | null
  isLoading: boolean
  setUser: (user: User | null) => void
  clearUser: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: true,
  setUser: (user) => set({ user, isLoading: false }),
  clearUser: () => set({ user: null, isLoading: false }),
}))
