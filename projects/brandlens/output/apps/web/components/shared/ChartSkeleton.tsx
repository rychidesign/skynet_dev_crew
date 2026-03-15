import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"

interface ChartSkeletonProps {
  className?: string
}

export function ChartSkeleton({ className }: ChartSkeletonProps) {
  return (
    <div className={cn("flex flex-col gap-4 w-full h-[300px]", className)}>
      <Skeleton className="h-full w-full rounded-xl" />
    </div>
  )
}
