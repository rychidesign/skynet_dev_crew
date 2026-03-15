"use client";

import { useState } from "react";
import { Plus, Trash2, DatabaseZap } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { createBrowserClient } from "@supabase/ssr";
import { updateCompanyFields } from "@/lib/services/companyService";

interface FactsEditorProps {
  initialFacts: Record<string, string>;
  companyId: string;
}

export function FactsEditor({ initialFacts, companyId }: FactsEditorProps) {
  // Translate initial facts dictionary into an array of {key, value} objects
  const [facts, setFacts] = useState<{ key: string; value: string }[]>(
    Object.entries(initialFacts || {}).map(([key, value]) => ({ key, value }))
  );
  const [isLoading, setIsLoading] = useState(false);

  const supabase = createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );

  const saveFactsToDb = async (newFactsArray: { key: string; value: string }[]) => {
    setIsLoading(true);
    // Convert array back to object dictionary
    const factsObject = newFactsArray.reduce((acc, curr) => {
      if (curr.key.trim()) {
        acc[curr.key.trim()] = curr.value.trim();
      }
      return acc;
    }, {} as Record<string, string>);

    try {
      await updateCompanyFields(supabase, companyId, { facts: factsObject });
      setFacts(newFactsArray);
    } catch (error) {
      console.error("Failed to update facts", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFactChange = (index: number, field: "key" | "value", value: string) => {
    const newFacts = [...facts];
    newFacts[index][field] = value;
    setFacts(newFacts);
  };

  const removeFact = (index: number) => {
    const newFacts = facts.filter((_, i) => i !== index);
    saveFactsToDb(newFacts);
  };

  const addEmptyFact = () => {
    setFacts([...facts, { key: "", value: "" }]);
  };

  const handleSave = () => {
    // Filter out completely empty rows before saving
    const validFacts = facts.filter((f) => f.key.trim() || f.value.trim());
    saveFactsToDb(validFacts);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <DatabaseZap className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-medium">Ground Truth Facts</h3>
        </div>
        <Button variant="outline" size="sm" onClick={handleSave} disabled={isLoading}>
          {isLoading ? "Saving..." : "Save Facts"}
        </Button>
      </div>

      <p className="text-xs text-muted-foreground">
        Define key facts about the company. The AI uses these to detect hallucinations in search results.
      </p>

      <div className="space-y-3 pt-2">
        {facts.map((fact, index) => (
          <div key={index} className="flex gap-2 items-center">
            <Input
              placeholder="Key (e.g. Founding Year)"
              value={fact.key}
              onChange={(e) => handleFactChange(index, "key", e.target.value)}
              disabled={isLoading}
              className="flex-1"
            />
            <Input
              placeholder="Value (e.g. 2015)"
              value={fact.value}
              onChange={(e) => handleFactChange(index, "value", e.target.value)}
              disabled={isLoading}
              className="flex-1"
            />
            <Button
              variant="ghost"
              size="icon"
              onClick={() => removeFact(index)}
              disabled={isLoading}
              className="text-muted-foreground hover:text-destructive shrink-0"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        ))}

        {facts.length === 0 && (
          <p className="text-sm text-muted-foreground italic border border-dashed rounded-md p-4 text-center">
            No facts defined yet. Add some to improve hallucination detection.
          </p>
        )}
      </div>

      <Button
        variant="ghost"
        size="sm"
        className="w-full mt-2 border border-dashed"
        onClick={addEmptyFact}
        disabled={isLoading}
      >
        <Plus className="h-4 w-4 mr-2" />
        Add Fact
      </Button>
    </div>
  );
}
