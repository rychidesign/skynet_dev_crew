"use client"

import { useOrgStore } from "@/stores/orgStore"
import { Lock } from "lucide-react"
import { Button } from "@/components/ui/button"
import Link from "next/link"
import { cn } from "@/lib/utils"

interface PlanGateProps {
  requiredPlan: "pro" | "enterprise"
  feature: string
  children: React.ReactNode
  fallback?: React.ReactNode
  className?: string
}

const PLAN_WEIGHTS: Record<string, number> = {
  free: 0,
  pro: 1,
  enterprise: 2,
}

export function PlanGate({
  requiredPlan,
  feature,
  children,
  fallback,
  className,
}: PlanGateProps) {
  const { activeOrg } = useOrgStore()

  const currentPlan = activeOrg?.plan || "free"
  const currentWeight = PLAN_WEIGHTS[currentPlan] ?? 0
  const requiredWeight = PLAN_WEIGHTS[requiredPlan] ?? 1

  const hasAccess = currentWeight >= requiredWeight

  if (hasAccess) {
    return <>{children}</>
  }

  // If user doesn't have access
  if (fallback) {
    return <>{fallback}</>
  }

  return (
    <div className={cn("relative group overflow-hidden rounded-xl border bg-card", className)}>
      {/* Blurred background content */}
      <div className="absolute inset-0 opacity-40 blur-sm pointer-events-none select-none transition-all duration-300">
        {children}
      </div>

      {/* Overlay CTA */}
      <div className="relative z-10 flex flex-col items-center justify-center h-full min-h-[200px] p-6 text-center bg-background/50 backdrop-blur-[2px]">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted mb-4">
          <Lock className="h-6 w-6 text-muted-foreground" />
        </div>
        <h3 className="text-lg font-semibold tracking-tight mb-2">
          {feature}
        </h3>
        <p className="text-sm text-muted-foreground mb-6 max-w-[250px]">
          Upgrade to the {requiredPlan === 'enterprise' ? 'Enterprise' : 'Pro'} plan to unlock this feature and supercharge your audits.
        </p>
        <Button asChild>
          <Link href="/settings">
            Upgrade to {requiredPlan === 'enterprise' ? 'Enterprise' : 'Pro'}
          </Link>
        </Button>
      </div>
    </div>
  )
}
