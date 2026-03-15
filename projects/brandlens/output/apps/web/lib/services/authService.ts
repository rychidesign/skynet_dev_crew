import { type SupabaseClient } from '@supabase/supabase-js'

export async function loginWithEmail(supabase: SupabaseClient, email: string, password: string) {
  return supabase.auth.signInWithPassword({ email, password })
}

export async function signupWithEmail(supabase: SupabaseClient, email: string, password: string) {
  return supabase.auth.signUp({ email, password })
}

export async function signInWithGoogle(supabase: SupabaseClient, redirectTo: string) {
  return supabase.auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo,
    },
  })
}

export async function resetPasswordForEmail(supabase: SupabaseClient, email: string, redirectTo: string) {
  return supabase.auth.resetPasswordForEmail(email, {
    redirectTo,
  })
}

export async function updatePassword(supabase: SupabaseClient, newPassword: string) {
  return supabase.auth.updateUser({ password: newPassword })
}
