import Link from "next/link";
import { Building2, Globe, Activity } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { getScoreColor } from "@/lib/utils/score";
import { CompanyWithLastAudit } from "@/lib/services/companyService";

interface CompanyCardProps {
  company: CompanyWithLastAudit;
}

export function CompanyCard({ company }: CompanyCardProps) {
  const { text: scoreTextColor, bg: scoreBgColor } = company.lastAuditScore !== null
    ? getScoreColor(company.lastAuditScore)
    : { text: "text-muted-foreground", bg: "bg-muted" };

  return (
    <Card className="hover:border-primary/50 transition-colors">
      <CardHeader className="pb-3">
        <div className="flex justify-between items-start">
          <CardTitle className="text-xl font-bold line-clamp-1">
            <Link href={`/companies/${company.id}`} className="hover:underline">
              {company.name}
            </Link>
          </CardTitle>
          <div className="flex items-center justify-center min-w-[3.5rem] h-8 px-2 rounded-full border bg-muted/50">
             {company.lastAuditScore !== null ? (
              <span className={`text-sm font-semibold ${scoreTextColor}`}>
                {company.lastAuditScore.toFixed(0)}
              </span>
            ) : (
              <span className="text-xs text-muted-foreground font-medium">N/A</span>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2 text-sm text-muted-foreground">
          {company.domain && (
            <div className="flex items-center gap-2">
              <Globe className="h-4 w-4 shrink-0" />
              <span className="truncate">{company.domain}</span>
            </div>
          )}
          {company.industry && (
            <div className="flex items-center gap-2">
              <Building2 className="h-4 w-4 shrink-0" />
              <span className="truncate">{company.industry}</span>
            </div>
          )}
        </div>
        
        <div className="pt-4 border-t flex items-center gap-2 text-xs">
            <Activity className="h-4 w-4 text-muted-foreground shrink-0" />
            <span className="text-muted-foreground">Last audit:</span>
            <span className="font-medium truncate">
                {company.lastAuditDate 
                  ? new Date(company.lastAuditDate).toLocaleDateString() 
                  : "No audits yet"}
            </span>
        </div>
      </CardContent>
    </Card>
  );
}
