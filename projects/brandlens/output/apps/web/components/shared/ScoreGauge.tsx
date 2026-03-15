import { getScoreColor, getRatingLabel } from '@/lib/utils/score'
import { cn } from '@/lib/utils'

interface ScoreGaugeProps {
  score: number
  size?: number
  strokeWidth?: number
  showLabel?: boolean
  className?: string
}

export function ScoreGauge({
  score,
  size = 120,
  strokeWidth = 8,
  showLabel = true,
  className,
}: ScoreGaugeProps) {
  // SVG circle calculations
  const radius = (size - strokeWidth) / 2
  const circumference = radius * 2 * Math.PI
  const safeScore = Math.min(Math.max(score, 0), 100)
  const offset = circumference - (safeScore / 100) * circumference

  const colors = getScoreColor(safeScore)
  const label = getRatingLabel(safeScore)

  return (
    <div className={cn("relative flex flex-col items-center justify-center", className)} style={{ width: size, height: size }}>
      <svg width={size} height={size} className="rotate-[-90deg]">
        {/* Background circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="transparent"
          strokeWidth={strokeWidth}
          className="stroke-muted"
        />
        {/* Foreground circle */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="transparent"
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className={cn("transition-all duration-1000 ease-out", colors.stroke)}
        />
      </svg>
      
      {/* Absolute positioned content inside the circle */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={cn("text-3xl font-bold tracking-tighter", colors.text)}>
          {safeScore.toFixed(0)}
        </span>
        {showLabel && (
          <span className={cn("text-xs font-medium uppercase tracking-wider mt-1", colors.text)}>
            {label}
          </span>
        )}
      </div>
    </div>
  )
}
