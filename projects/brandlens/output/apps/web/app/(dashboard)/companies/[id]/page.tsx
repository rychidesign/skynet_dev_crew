import { notFound } from "next/navigation";
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { getCompanyDetail } from "@/lib/services/companyService";
import { CompanyForm } from "@/components/company/CompanyForm";
import { FactsEditor } from "@/components/company/FactsEditor";
import { CompetitorList } from "@/components/company/CompetitorList";
import { TopicTags } from "@/components/company/TopicTags";
import { TrendChart } from "@/components/shared/TrendChart";
import { getScoreColor } from "@/lib/utils/score";
import Link from "next/link";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export const metadata = {
  title: "Company Detail | BrandLens",
  description: "View and edit company facts, competitors, and audit history.",
};

export default async function CompanyDetailPage({ params }: { params: { id: string } }) {
  const cookieStore = cookies();
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        get(name: string) {
          return cookieStore.get(name)?.value;
        },
      },
    }
  );

  let company;
  try {
    company = await getCompanyDetail(supabase, params.id);
  } catch (error) {
    console.error("Failed to fetch company details:", error);
    notFound();
  }

  if (!company) {
    notFound();
  }

  return (
    <div className="container mx-auto py-8 space-y-8 max-w-7xl">
      <div className="flex justify-between items-center mb-6 border-b pb-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{company.name}</h1>
          <p className="text-muted-foreground mt-1">
            {company.domain || "No domain set"} • {company.industry || "No industry set"}
          </p>
        </div>
        <Link
          href={`/audits/new?companyId=${company.id}`}
          className="bg-primary text-primary-foreground hover:bg-primary/90 px-4 py-2 rounded-md font-medium text-sm transition-colors"
        >
          Run Audit
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Left Column: Basic Details and Trend */}
        <div className="space-y-8">
          <div className="bg-card text-card-foreground border rounded-xl p-6 shadow-sm">
             <CompanyForm company={company} />
          </div>

          <div className="bg-card text-card-foreground border rounded-xl p-6 shadow-sm">
            <h3 className="text-lg font-semibold mb-4">Score Trend</h3>
             {company.metricTimeSeries.length > 0 ? (
                <div className="h-[300px]">
                   <TrendChart data={company.metricTimeSeries} />
                </div>
             ) : (
                <div className="h-[200px] flex items-center justify-center border border-dashed rounded-lg bg-muted/20">
                   <p className="text-sm text-muted-foreground">Not enough data to display trend.</p>
                </div>
             )}
          </div>
        </div>

        {/* Right Column: Ground Truth Configuration */}
        <div className="space-y-8">
          <div className="bg-card text-card-foreground border rounded-xl p-6 shadow-sm">
            <FactsEditor initialFacts={company.facts} companyId={company.id} />
          </div>

          <div className="bg-card text-card-foreground border rounded-xl p-6 shadow-sm grid gap-6 sm:grid-cols-2">
            <CompetitorList initialCompetitors={company.competitors} companyId={company.id} />
            <TopicTags initialTopics={company.coreTopics} companyId={company.id} />
          </div>
        </div>
      </div>

      {/* Bottom Section: Audit History */}
      <div className="bg-card text-card-foreground border rounded-xl p-6 shadow-sm mt-8">
        <h3 className="text-xl font-bold mb-6">Audit History</h3>
        {company.audits.length > 0 ? (
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Score</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {company.audits.map((audit) => {
                  const scoreColors = audit.globalGeoScore !== null ? getScoreColor(audit.globalGeoScore) : null;
                  return (
                    <TableRow key={audit.id}>
                      <TableCell className="font-medium">
                        <Link href={`/audits/${audit.id}`} className="hover:underline text-primary">
                          {new Date(audit.createdAt).toLocaleDateString()} {new Date(audit.createdAt).toLocaleTimeString()}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <span className="capitalize text-muted-foreground">{audit.status}</span>
                      </TableCell>
                      <TableCell className="text-right font-semibold">
                         {audit.globalGeoScore !== null ? (
                            <span className={scoreColors?.text}>
                               {audit.globalGeoScore.toFixed(0)}
                            </span>
                         ) : (
                            <span className="text-muted-foreground">N/A</span>
                         )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        ) : (
          <div className="text-center py-8 border border-dashed rounded-lg text-muted-foreground">
            No audits have been performed for this company yet.
          </div>
        )}
      </div>
    </div>
  );
}
