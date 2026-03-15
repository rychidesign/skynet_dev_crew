"use client"

import { useRouter } from "next/navigation"
import { createClient } from "@/lib/supabase/client"
import { useOrgStore } from "@/stores/orgStore"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"

interface TopBarProps {
  userEmail?: string
}

export function TopBar({ userEmail }: TopBarProps) {
  const router = useRouter()
  const supabase = createClient()
  const { activeOrg, organizations, setActiveOrg } = useOrgStore()

  const handleLogout = async () => {
    await supabase.auth.signOut()
    router.push("/login")
    router.refresh()
  }

  // Fallback initial
  const initial = userEmail ? userEmail.charAt(0).toUpperCase() : "U"

  return (
    <header className="flex h-14 items-center gap-4 border-b bg-muted/10 px-4 lg:h-[60px] lg:px-6 justify-between">
      
      {/* Organization Switcher */}
      <div className="flex items-center gap-2">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="h-8 gap-2 px-2 text-sm font-medium">
              <span className="truncate max-w-[150px]">
                {activeOrg ? activeOrg.name : "Select Workspace"}
              </span>
              <span className="text-muted-foreground text-xs ml-2">
                {activeOrg?.plan === 'pro' ? 'PRO' : activeOrg?.plan === 'enterprise' ? 'ENT' : 'FREE'}
              </span>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-[200px]">
            <DropdownMenuLabel>Workspaces</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {organizations.map((org) => (
              <DropdownMenuItem 
                key={org.id} 
                onClick={() => setActiveOrg(org)}
                className="cursor-pointer flex justify-between"
              >
                <span className="truncate">{org.name}</span>
                {activeOrg?.id === org.id && <span className="text-xs text-primary">✓</span>}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* User Menu */}
      <div className="flex items-center gap-4">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="rounded-full">
              <Avatar className="h-8 w-8 border">
                <AvatarFallback>{initial}</AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel className="font-normal">
              <div className="flex flex-col space-y-1">
                <p className="text-sm font-medium leading-none">Account</p>
                <p className="text-xs leading-none text-muted-foreground">
                  {userEmail}
                </p>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => router.push('/settings')} className="cursor-pointer">
              Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout} className="cursor-pointer text-red-600 focus:text-red-600">
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}
