import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { getCompanies } from "@/lib/services/companyService";
import { CreateCompanyDialog } from "@/components/company/CreateCompanyDialog";
import { CompanyCard } from "@/components/company/CompanyCard";
import { Building2 } from "lucide-react";
import { Suspense } from "react";

export const metadata = {
  title: "Companies | BrandLens",
  description: "Manage your companies and view their latest audit scores.",
};

async function getActiveOrganizationId(supabase: any) {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) throw new Error("Unauthorized");

  const { data: member, error } = await supabase
    .from('organization_members')
    .select('organization_id')
    .eq('user_id', user.id)
    .limit(1)
    .single();

  if (error || !member) throw new Error("No organization found");

  return member.organization_id;
}

async function CompaniesList() {
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

  const orgId = await getActiveOrganizationId(supabase);
  const companies = await getCompanies(supabase, orgId);

  if (companies.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] bg-muted/20 border rounded-lg border-dashed">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-muted">
          <Building2 className="h-10 w-10 text-muted-foreground" />
        </div>
        <h2 className="mt-6 text-xl font-semibold">No companies yet</h2>
        <p className="mt-2 text-center text-sm text-muted-foreground max-w-sm">
          Add a company to start tracking its brand visibility across AI search engines.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {companies.map((company) => (
        <CompanyCard key={company.id} company={company} />
      ))}
    </div>
  );
}

export default function CompaniesPage() {
  return (
    <div className="container mx-auto py-8 space-y-8 max-w-7xl">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Companies</h1>
          <p className="text-muted-foreground mt-1">
            Manage the brands you monitor and audit.
          </p>
        </div>
        <CreateCompanyDialog />
      </div>

      <Suspense fallback={
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-[200px] rounded-xl border bg-card text-card-foreground shadow animate-pulse" />
          ))}
        </div>
      }>
        <CompaniesList />
      </Suspense>
    </div>
  );
}
