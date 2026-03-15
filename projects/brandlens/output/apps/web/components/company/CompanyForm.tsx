"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createBrowserClient } from "@supabase/ssr";
import { updateCompany } from "@/lib/services/companyService";
import { CompanyRow } from "@shared/types/database";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export function CompanyForm({ company }: { company: CompanyRow }) {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const supabase = createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    const formData = new FormData(e.currentTarget);
    const updates = {
      name: formData.get("name") as string,
      domain: formData.get("domain") as string,
      industry: formData.get("industry") as string,
      description: formData.get("description") as string,
    };

    try {
      await updateCompany(supabase, company.id, updates);
      router.refresh();
    } catch (err: any) {
      setError(err.message || "Failed to update company");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <h3 className="text-lg font-semibold">Basic Details</h3>
      
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <label htmlFor="name" className="text-sm font-medium">Name</label>
          <Input id="name" name="name" defaultValue={company.name} required disabled={isLoading} />
        </div>
        <div className="space-y-2">
          <label htmlFor="domain" className="text-sm font-medium">Domain</label>
          <Input id="domain" name="domain" defaultValue={company.domain || ""} disabled={isLoading} />
        </div>
        <div className="space-y-2 sm:col-span-2">
          <label htmlFor="industry" className="text-sm font-medium">Industry</label>
          <Input id="industry" name="industry" defaultValue={company.industry || ""} disabled={isLoading} />
        </div>
      </div>

      <div className="space-y-2">
        <label htmlFor="description" className="text-sm font-medium">Description</label>
        <Textarea 
          id="description" 
          name="description" 
          defaultValue={company.description || ""} 
          className="min-h-[100px]"
          disabled={isLoading} 
        />
      </div>

      {error && <div className="text-sm text-red-500 bg-red-50 p-2 rounded">{error}</div>}

      <div className="flex justify-end">
        <Button type="submit" disabled={isLoading}>
          {isLoading ? "Saving..." : "Save Changes"}
        </Button>
      </div>
    </form>
  );
}
