"use client";

import { useState } from "react";
import { Plus, X, Swords } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { createBrowserClient } from "@supabase/ssr";
import { updateCompanyFields } from "@/lib/services/companyService";

interface CompetitorListProps {
  initialCompetitors: string[];
  companyId: string;
}

export function CompetitorList({ initialCompetitors, companyId }: CompetitorListProps) {
  const [competitors, setCompetitors] = useState<string[]>(initialCompetitors || []);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const supabase = createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );

  const saveCompetitors = async (newCompetitors: string[]) => {
    setIsLoading(true);
    try {
      await updateCompanyFields(supabase, companyId, { competitors: newCompetitors });
      setCompetitors(newCompetitors);
    } catch (error) {
      console.error("Failed to update competitors", error);
    } finally {
      setIsLoading(false);
    }
  };

  const addCompetitor = () => {
    const newCompetitor = inputValue.trim();
    if (newCompetitor && !competitors.includes(newCompetitor)) {
      const newCompetitors = [...competitors, newCompetitor];
      setInputValue("");
      saveCompetitors(newCompetitors);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addCompetitor();
    }
  };

  const removeCompetitor = (competitorToRemove: string) => {
    const newCompetitors = competitors.filter((c) => c !== competitorToRemove);
    saveCompetitors(newCompetitors);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Swords className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-medium">Competitors</h3>
      </div>
      
      <div className="space-y-2">
        {competitors.map((competitor) => (
          <div key={competitor} className="flex items-center justify-between bg-card border px-3 py-2 rounded-md">
            <span className="text-sm">{competitor}</span>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6 text-muted-foreground hover:text-destructive"
              onClick={() => removeCompetitor(competitor)}
              disabled={isLoading}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        ))}
        {competitors.length === 0 && (
          <p className="text-sm text-muted-foreground italic">No competitors defined.</p>
        )}
      </div>

      <div className="flex gap-2 max-w-md pt-2">
        <Input
          placeholder="e.g. Acme Corp or acme.com"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
        />
        <Button onClick={addCompetitor} disabled={isLoading || !inputValue.trim()} size="icon" variant="outline">
          <Plus className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
