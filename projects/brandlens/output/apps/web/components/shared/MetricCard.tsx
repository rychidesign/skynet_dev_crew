import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { PlanGate } from "@/components/shared/PlanGate"
import { getScoreColor } from "@/lib/utils/score"
import { cn } from "@/lib/utils"

interface MetricCardProps {
  metricId: string
  name: string
  score: number | null
  isLocked?: boolean
  className?: string
}

export function MetricCard({
  metricId,
  name,
  score,
  isLocked = false,
  className,
}: MetricCardProps) {
  // If explicitly locked or score is null (meaning backend omitted it due to plan limits)
  const locked = isLocked || score === null

  const content = (
    <Card className={cn("flex flex-col h-full", className)}>
      <CardHeader className="pb-2 flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-sm font-medium">{name}</CardTitle>
        <span className="font-mono text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
          {metricId}
        </span>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col justify-end">
        {locked ? (
          <div className="space-y-2">
            <div className="text-2xl font-bold tracking-tight text-muted-foreground">--</div>
            <div className="h-2 w-full bg-muted rounded-full overflow-hidden"></div>
          </div>
        ) : (
          <div className="space-y-2">
            <div className={cn("text-2xl font-bold tracking-tight", getScoreColor(score).text)}>
              {score.toFixed(1)}
            </div>
            {/* Simple static progress bar representation */}
            <div className="h-2 w-full bg-muted rounded-full overflow-hidden flex">
              <div 
                className={cn("h-full", getScoreColor(score).bg.replace('bg-', 'bg-').replace('50', '500'))} // Quick hack to use the 500 variant for the fill
                style={{ width: `${Math.min(Math.max(score, 0), 100)}%` }}
              />
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )

  if (locked) {
    return (
      <PlanGate requiredPlan="pro" feature={name}>
        {content}
      </PlanGate>
    )
  }

  return content
}
