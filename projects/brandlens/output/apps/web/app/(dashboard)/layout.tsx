import { redirect } from "next/navigation"
import { createClient } from "@/lib/supabase/server"
import { AppShell } from "@/components/layout/AppShell"
import { type OrgBase } from "@/stores/orgStore"

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const supabase = await createClient()

  // 1. Authenticate user
  const { data: { user }, error: authError } = await supabase.auth.getUser()

  if (authError || !user) {
    redirect("/login")
  }

  // 2. Fetch user's organizations via organization_members
  // We need to fetch the organization details by joining or querying twice
  // Using Supabase related tables syntax:
  const { data: memberData, error: memberError } = await supabase
    .from("organization_members")
    .select(`
      role,
      organizations (
        id,
        name,
        slug,
        plan
      )
    `)
    .eq("user_id", user.id)

  if (memberError) {
    console.error("Error fetching organizations:", memberError)
    // Could redirect to error page, but for now fallback to empty
  }

  // 3. Format the organizations array for the client store
  const organizations: OrgBase[] = []
  
  if (memberData && memberData.length > 0) {
    // Need to handle the fact that Supabase returns a generic structure
    // that might be an array or an object depending on relations
    for (const membership of memberData) {
      const org = membership.organizations as any
      if (org) {
        organizations.push({
          id: org.id,
          name: org.name,
          slug: org.slug,
          plan: org.plan || "free",
        })
      }
    }
  }

  // 4. Redirect to onboarding if no organizations are found
  if (organizations.length === 0) {
    redirect("/onboarding")
  }

  return (
    <AppShell initialOrgs={organizations} userEmail={user.email}>
      {children}
    </AppShell>
  )
}
