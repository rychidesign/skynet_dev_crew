"use client"

import { useOrgStore } from "@/stores/orgStore"
import { type CompanyWithLastAudit } from "@/lib/services/companyService"
import { CompanyCard } from "@/components/company/CompanyCard"
import { CreateCompanyDialog } from "@/components/company/CreateCompanyDialog"
import { Building2 } from "lucide-react"

interface CompanyListProps {
  initialCompanies: CompanyWithLastAudit[]
}

export function CompanyList({ initialCompanies }: CompanyListProps) {
  const { activeOrg } = useOrgStore()

  const filteredCompanies = initialCompanies.filter(
    (company) => activeOrg && company.organizationId === activeOrg.id
  )

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Companies</h1>
          <p className="text-muted-foreground mt-1">
            Manage brands and competitors in your workspace.
          </p>
        </div>
        <CreateCompanyDialog />
      </div>

      {!activeOrg ? (
        <div className="flex flex-col items-center justify-center p-12 text-center border rounded-xl bg-muted/20 border-dashed">
          <Building2 className="h-10 w-10 text-muted-foreground mb-4 opacity-50" />
          <h3 className="text-lg font-semibold">No workspace selected</h3>
          <p className="text-sm text-muted-foreground mt-1 max-w-sm">
            Please select an organization from the top menu to view its companies.
          </p>
        </div>
      ) : filteredCompanies.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-12 text-center border rounded-xl bg-muted/20 border-dashed">
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-muted mb-4">
            <Building2 className="h-10 w-10 text-muted-foreground opacity-50" />
          </div>
          <h3 className="text-xl font-semibold mb-2">No companies found</h3>
          <p className="text-sm text-muted-foreground mb-6 max-w-sm">
            You haven&apos;t added any companies to this workspace yet. Add your first brand to start auditing.
          </p>
          <CreateCompanyDialog />
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {filteredCompanies.map((company) => (
            <CompanyCard key={company.id} company={company} />
          ))}
        </div>
      )}
    </div>
  )
}
