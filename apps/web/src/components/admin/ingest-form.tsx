"use client";

import { Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export function IngestForm({ onSubmit }: { onSubmit: (url: string) => Promise<void> }) {
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    const u = url.trim();
    if (!u) return;
    setBusy(true);
    try {
      await onSubmit(u);
      setUrl("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Ingest a YouTube talk</CardTitle>
      </CardHeader>
      <CardContent>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
          className="flex flex-col gap-2 sm:flex-row"
        >
          <Input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://youtu.be/…"
            aria-label="YouTube URL"
            className="flex-1"
          />
          <Button type="submit" disabled={busy || !url.trim()} className="gap-1">
            <Plus className="size-4" /> {busy ? "Queuing…" : "Queue ingestion"}
          </Button>
        </form>
        <p className="mt-2 text-xs text-muted-foreground">
          Queues a YouTube job for download, frame extraction, transcription, and artifact storage.
          Embeddings and Pinecone upsert land in Phase 3.
        </p>
      </CardContent>
    </Card>
  );
}
