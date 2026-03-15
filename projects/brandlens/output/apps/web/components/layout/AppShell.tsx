"use client"

import { useEffect, useRef } from "react"
import { Sidebar } from "@/components/layout/Sidebar"
import { TopBar } from "@/components/layout/TopBar"
import { useOrgStore, type OrgBase } from "@/stores/orgStore"

interface AppShellProps {
  children: React.ReactNode
  initialOrgs: OrgBase[]
  userEmail?: string
}

export function AppShell({ children, initialOrgs, userEmail }: AppShellProps) {
  const { organizations, setOrganizations, setActiveOrg, activeOrg } = useOrgStore()
  
  // Use a ref to prevent unnecessary re-renders when setting initial state
  const isHydrated = useRef(false)

  useEffect(() => {
    if (!isHydrated.current && initialOrgs.length > 0) {
      setOrganizations(initialOrgs)
      
      // If we don't have an active org set, set the first one
      if (!activeOrg) {
        setActiveOrg(initialOrgs[0])
      }
      
      isHydrated.current = true
    }
  }, [initialOrgs, setOrganizations, setActiveOrg, activeOrg])

  return (
    <div className="grid min-h-screen w-full md:grid-cols-[220px_1fr] lg:grid-cols-[280px_1fr]">
      <Sidebar />
      <div className="flex flex-col w-full overflow-hidden">
        <TopBar userEmail={userEmail} />
        <main className="flex flex-1 flex-col gap-4 p-4 lg:gap-6 lg:p-6 overflow-auto">
          {children}
        </main>
      </div>
    </div>
  )
}
