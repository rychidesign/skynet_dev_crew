"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { createClient } from "@/lib/supabase/client"
import { setupNewOrganization, type OnboardingPayload } from "@/lib/services/organizationService"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Loader2 } from "lucide-react"

export default function OnboardingPage() {
  const router = useRouter()
  const supabase = createClient()
  
  const [userId, setUserId] = useState<string | null>(null)
  const [isInitializing, setIsInitializing] = useState(true)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [orgName, setOrgName] = useState("")
  const [companyName, setCompanyName] = useState("")
  const [companyDomain, setCompanyDomain] = useState("")
  const [companyIndustry, setCompanyIndustry] = useState("")

  useEffect(() => {
    async function checkUser() {
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) {
        router.push("/login")
        return
      }
      setUserId(user.id)
      setIsInitializing(false)
    }
    
    checkUser()
  }, [router, supabase.auth])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!userId) return

    setIsLoading(true)
    setError(null)

    try {
      const payload: OnboardingPayload = {
        orgName,
        companyName,
        companyDomain: companyDomain.trim() !== "" ? companyDomain : undefined,
        companyIndustry: companyIndustry.trim() !== "" ? companyIndustry : undefined,
      }

      await setupNewOrganization(supabase, payload, userId)
      
      // Navigate to dashboard root which will handle subsequent initialization
      router.push("/")
      router.refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred during setup.")
      setIsLoading(false)
    }
  }

  if (isInitializing) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-muted/30">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/30 p-4">
      <Card className="w-full max-w-lg mx-auto">
        <CardHeader className="space-y-1">
          <CardTitle className="text-2xl font-bold text-center">Welcome to BrandLens</CardTitle>
          <CardDescription className="text-center">
            Let&apos;s set up your workspace and your first brand to audit.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            
            <div className="space-y-4">
              <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
                Organization Details
              </h3>
              <div className="space-y-2">
                <Label htmlFor="orgName">Organization Name <span className="text-red-500">*</span></Label>
                <Input 
                  id="orgName" 
                  placeholder="e.g. Acme Corp" 
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  required 
                />
                <p className="text-xs text-muted-foreground">
                  This is your team&apos;s shared workspace.
                </p>
              </div>
            </div>

            <div className="space-y-4">
              <h3 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
                First Brand (Company)
              </h3>
              <div className="space-y-2">
                <Label htmlFor="companyName">Brand Name <span className="text-red-500">*</span></Label>
                <Input 
                  id="companyName" 
                  placeholder="e.g. Acme AI Solutions" 
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  required 
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="companyDomain">Domain (optional)</Label>
                  <Input 
                    id="companyDomain" 
                    placeholder="example.com" 
                    value={companyDomain}
                    onChange={(e) => setCompanyDomain(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="companyIndustry">Industry (optional)</Label>
                  <Input 
                    id="companyIndustry" 
                    placeholder="e.g. Software" 
                    value={companyIndustry}
                    onChange={(e) => setCompanyIndustry(e.target.value)}
                  />
                </div>
              </div>
            </div>

            {error && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-600 text-sm font-medium rounded-md">
                {error}
              </div>
            )}

            <Button type="submit" className="w-full" disabled={isLoading || !orgName || !companyName}>
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Setting up your workspace...
                </>
              ) : (
                "Complete Setup"
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
