"use client";

import { LoaderCircle, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function SearchBar({
  value,
  onChange,
  onSubmit,
  loading,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  loading: boolean;
}) {
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
      className="flex w-full items-center gap-2 rounded-2xl border border-border/80 bg-card/80 p-2 shadow-sm backdrop-blur-sm"
    >
      <div className="relative flex-1">
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Ask about a moment… e.g. where do they explain salary negotiation?"
          aria-label="Search query"
          className="h-11 border-0 bg-transparent pl-9 text-base shadow-none focus-visible:ring-0"
        />
      </div>
      <Button type="submit" size="lg" className="h-11" disabled={loading || !value.trim()}>
        {loading ? (
          <>
            <LoaderCircle className="size-4 animate-spin" aria-hidden /> Searching…
          </>
        ) : (
          "Search"
        )}
      </Button>
    </form>
  );
}
