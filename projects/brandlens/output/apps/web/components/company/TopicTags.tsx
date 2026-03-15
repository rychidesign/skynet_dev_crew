"use client";

import { useState } from "react";
import { Tag, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { createBrowserClient } from "@supabase/ssr";
import { updateCompanyFields } from "@/lib/services/companyService";

interface TopicTagsProps {
  initialTopics: string[];
  companyId: string;
}

export function TopicTags({ initialTopics, companyId }: TopicTagsProps) {
  const [topics, setTopics] = useState<string[]>(initialTopics || []);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const supabase = createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );

  const saveTopics = async (newTopics: string[]) => {
    setIsLoading(true);
    try {
      await updateCompanyFields(supabase, companyId, { coreTopics: newTopics });
      setTopics(newTopics);
    } catch (error) {
      console.error("Failed to update topics", error);
      // Revert optimism if failed
      setTopics(topics); 
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const newTopic = inputValue.trim();
      if (newTopic && !topics.includes(newTopic)) {
        const newTopics = [...topics, newTopic];
        setInputValue("");
        saveTopics(newTopics);
      }
    }
  };

  const removeTopic = (topicToRemove: string) => {
    const newTopics = topics.filter((t) => t !== topicToRemove);
    saveTopics(newTopics);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Tag className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-medium">Core Topics</h3>
      </div>
      
      <div className="flex flex-wrap gap-2">
        {topics.map((topic) => (
          <div
            key={topic}
            className="flex items-center gap-1 bg-secondary text-secondary-foreground px-2 py-1 rounded-md text-sm"
          >
            <span>{topic}</span>
            <button
              onClick={() => removeTopic(topic)}
              disabled={isLoading}
              className="text-muted-foreground hover:text-foreground disabled:opacity-50"
              aria-label={`Remove ${topic}`}
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        ))}
      </div>

      <Input
        placeholder="Add a topic and press Enter..."
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={isLoading}
        className="max-w-md"
      />
      <p className="text-xs text-muted-foreground">
        Press Enter to add keywords representing the brand's key themes.
      </p>
    </div>
  );
}
