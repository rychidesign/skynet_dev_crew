"use client"

import { useState } from "react"
import Link from "next/link"
import { createClient } from "@/lib/supabase/client"
import { resetPasswordForEmail } from "@/lib/services/authService"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Loader2 } from "lucide-react"

export function ForgotPasswordForm() {
  const supabase = createClient()
  const [email, setEmail] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [isLoading, setIsLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    setError(null)
    setSuccess(false)
    
    const origin = typeof window !== 'undefined' ? window.location.origin : ''
    const { error: resetError } = await resetPasswordForEmail(supabase, email, `${origin}/reset-password`)
    
    if (resetError) {
      setError(resetError.message)
      setIsLoading(false)
      return
    }
    
    setSuccess(true)
    setIsLoading(false)
  }

  return (
    <Card className="w-full max-w-md mx-auto">
      <CardHeader className="space-y-1">
        <CardTitle className="text-2xl font-bold text-center">Reset password</CardTitle>
        <CardDescription className="text-center">
          Enter your email address and we will send you a password reset link
        </CardDescription>
      </CardHeader>
      <CardContent>
        {success ? (
          <div className="p-4 bg-green-50 text-green-600 text-sm font-medium rounded-md text-center">
            Check your email for a reset link.
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input 
                id="email" 
                type="email" 
                placeholder="m@example.com" 
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required 
              />
            </div>
            {error && (
              <div className="text-sm font-medium text-red-500">{error}</div>
            )}
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Send reset link
            </Button>
          </form>
        )}
      </CardContent>
      <CardFooter className="flex justify-center">
        <div className="text-sm text-muted-foreground">
          Remember your password?{" "}
          <Link href="/login" className="text-primary hover:underline font-medium">
            Sign in
          </Link>
        </div>
      </CardFooter>
    </Card>
  )
}
