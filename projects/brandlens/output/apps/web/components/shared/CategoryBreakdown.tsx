import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { getScoreColor } from "@/lib/utils/score"
import { cn } from "@/lib/utils"

export interface CategoryScores {
  entitySemantic: number | null
  citationsTrust: number | null
  contentTechnical: number | null
  reputationSentiment: number | null
}

interface CategoryBreakdownProps {
  scores: CategoryScores
  isLoading?: boolean
  className?: string
}

export function CategoryBreakdown({ scores, isLoading = false, className }: CategoryBreakdownProps) {
  const categories = [
    { id: "entitySemantic", title: "Entity & Semantic", score: scores.entitySemantic },
    { id: "citationsTrust", title: "Citations & Trust", score: scores.citationsTrust },
    { id: "contentTechnical", title: "Content & Technical", score: scores.contentTechnical },
    { id: "reputationSentiment", title: "Reputation & Sentiment", score: scores.reputationSentiment },
  ]

  return (
    <div className={cn("grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4", className)}>
      {categories.map((cat) => (
        <Card key={cat.id}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground line-clamp-1">
              {cat.title}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-8 w-16" />
            ) : cat.score !== null ? (
              <div className="flex items-baseline gap-2">
                <span className={cn("text-2xl font-bold tracking-tight", getScoreColor(cat.score).text)}>
                  {cat.score.toFixed(1)}
                </span>
                <span className="text-sm font-medium text-muted-foreground">/ 100</span>
              </div>
            ) : (
              <div className="text-2xl font-bold tracking-tight text-muted-foreground">
                N/A
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
