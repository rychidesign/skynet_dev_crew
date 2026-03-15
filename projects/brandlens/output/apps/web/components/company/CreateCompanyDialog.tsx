"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useOrgStore } from "@/stores/orgStore";
import { createBrowserClient } from "@supabase/ssr";
import { createCompany } from "@/lib/services/companyService";
import { Plus } from "lucide-react";

export function CreateCompanyDialog() {
  const router = useRouter();
  const activeOrg = useOrgStore((state) => state.activeOrg);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const supabase = createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!activeOrg?.id) return;

    setError(null);
    setIsLoading(true);

    const formData = new FormData(e.currentTarget);
    const name = formData.get("name") as string;
    const domain = formData.get("domain") as string;
    const industry = formData.get("industry") as string;
    const description = formData.get("description") as string;

    try {
      await createCompany(supabase, {
        organizationId: activeOrg.id,
        name,
        domain: domain || null,
        industry: industry || null,
        description: description || null,
        facts: {},
        competitors: [],
        coreTopics: [],
      });

      setIsOpen(false);
      router.refresh();
    } catch (err: any) {
      setError(err.message || "Failed to create company");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogTrigger asChild>
        <Button className="gap-2">
          <Plus className="h-4 w-4" />
          Add Company
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Add a new company</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-4">
          <div className="space-y-2">
            <label htmlFor="name" className="text-sm font-medium">
              Company Name <span className="text-red-500">*</span>
            </label>
            <Input id="name" name="name" placeholder="Acme Inc." required disabled={isLoading} />
          </div>
          
          <div className="space-y-2">
            <label htmlFor="domain" className="text-sm font-medium">
              Website Domain
            </label>
            <Input id="domain" name="domain" placeholder="acme.com" disabled={isLoading} />
          </div>

          <div className="space-y-2">
            <label htmlFor="industry" className="text-sm font-medium">
              Industry
            </label>
            <Input id="industry" name="industry" placeholder="Technology" disabled={isLoading} />
          </div>

          <div className="space-y-2">
            <label htmlFor="description" className="text-sm font-medium">
              Description
            </label>
            <Textarea 
              id="description" 
              name="description" 
              placeholder="Brief description of the company..."
              className="resize-none"
              rows={3}
              disabled={isLoading}
            />
          </div>

          {error && <div className="text-sm text-red-500 bg-red-50 p-2 rounded-md">{error}</div>}

          <div className="pt-4 flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setIsOpen(false)} disabled={isLoading}>
              Cancel
            </Button>
            <Button type="submit" disabled={isLoading || !activeOrg?.id}>
              {isLoading ? "Creating..." : "Create Company"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
