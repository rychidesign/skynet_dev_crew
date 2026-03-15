"use client"

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell
} from "recharts"
import { ChartSkeleton } from "@/components/shared/ChartSkeleton"
import { getScoreColor } from "@/lib/utils/score"

export interface PlatformDataPoint {
  platform: string
  score: number
  [key: string]: string | number
}

interface PlatformBarChartProps {
  data: PlatformDataPoint[]
  isLoading?: boolean
  height?: number
  useScoreColors?: boolean
}

export function PlatformBarChart({
  data,
  isLoading = false,
  height = 300,
  useScoreColors = true,
}: PlatformBarChartProps) {
  if (isLoading) {
    return <ChartSkeleton className={`h-[${height}px]`} />
  }

  if (!data || data.length === 0) {
    return (
      <div 
        className="flex items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground"
        style={{ height }}
      >
        No platform data available
      </div>
    )
  }

  return (
    <div style={{ height, width: "100%" }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          layout="vertical"
          data={data}
          margin={{
            top: 5,
            right: 30,
            left: 40,
            bottom: 5,
          }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="hsl(var(--border))" />
          <XAxis 
            type="number" 
            domain={[0, 100]} 
            tickLine={false} 
            axisLine={false} 
            tick={{ fill: "hsl(var(--muted-foreground))", fontSize: 12 }} 
          />
          <YAxis 
            dataKey="platform" 
            type="category" 
            tickLine={false} 
            axisLine={false} 
            tick={{ fill: "hsl(var(--foreground))", fontSize: 12, fontWeight: 500 }} 
          />
          <Tooltip 
            cursor={{ fill: "hsl(var(--muted))", opacity: 0.4 }}
            contentStyle={{ 
              backgroundColor: "hsl(var(--background))", 
              borderColor: "hsl(var(--border))",
              borderRadius: "var(--radius)",
              boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)"
            }} 
            itemStyle={{ color: "hsl(var(--foreground))" }}
            formatter={(value: number) => [value.toFixed(1), "Score"]}
          />
          <Bar 
            dataKey="score" 
            radius={[0, 4, 4, 0]} 
            barSize={24}
          >
            {data.map((entry, index) => {
              // Convert text color class (e.g., text-red-500) to actual hex/rgb variable for recharts
              // As a simple fallback without parsing tailwind config, we use CSS variables if defined
              // or fall back to primary color if useScoreColors is false
              
              let fillcolor = "hsl(var(--primary))"
              
              if (useScoreColors) {
                const colors = getScoreColor(entry.score)
                if (colors.text.includes('red')) fillcolor = "#ef4444"
                else if (colors.text.includes('orange')) fillcolor = "#f97316"
                else if (colors.text.includes('yellow')) fillcolor = "#eab308"
                else if (colors.text.includes('blue')) fillcolor = "#3b82f6"
                else if (colors.text.includes('green')) fillcolor = "#22c55e"
              }
              
              return <Cell key={`cell-${index}`} fill={fillcolor} />
            })}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
