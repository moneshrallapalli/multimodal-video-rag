"use client";

import { LoaderCircle, Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { IngestRequest } from "@/lib/types";

export function IngestForm({ onSubmit }: { onSubmit: (req: IngestRequest) => Promise<void> }) {
  const [url, setUrl] = useState("");
  const [frameInterval, setFrameInterval] = useState("");
  const [maxFrames, setMaxFrames] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    const u = url.trim();
    if (!u) return;
    setBusy(true);
    try {
      await onSubmit({
        youtube_url: u,
        frame_interval_seconds: frameInterval ? Number(frameInterval) : null,
        max_frames: maxFrames ? Number(maxFrames) : null,
      });
      setUrl("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="rounded-2xl border-border/80 shadow-sm">
      <CardHeader>
        <CardTitle className="text-base">Ingest a YouTube talk</CardTitle>
      </CardHeader>
      <CardContent>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
          className="flex flex-col gap-3"
        >
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://youtu.be/…"
              aria-label="YouTube URL"
              className="flex-1"
            />
            <Button type="submit" disabled={busy || !url.trim()} className="gap-1">
              {busy ? (
                <LoaderCircle className="size-4 animate-spin" aria-hidden />
              ) : (
                <Plus className="size-4" />
              )}
              {busy ? "Queuing…" : "Queue ingestion"}
            </Button>
          </div>
          <div className="flex gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">Frame interval (s)</span>
              <Input
                type="number"
                min={5}
                max={300}
                value={frameInterval}
                onChange={(e) => setFrameInterval(e.target.value)}
                placeholder="10"
                aria-label="Frame interval in seconds"
                className="w-28"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">Max frames</span>
              <Input
                type="number"
                min={1}
                max={200}
                value={maxFrames}
                onChange={(e) => setMaxFrames(e.target.value)}
                placeholder="200"
                aria-label="Maximum frames"
                className="w-28"
              />
            </label>
          </div>
          <p className="text-xs text-muted-foreground">
            Queues a YouTube job for download, frame extraction, transcription, artifact storage,
            embeddings, and Pinecone indexing. Frame controls override the global defaults (10s / 200
            frames).
          </p>
        </form>
      </CardContent>
    </Card>
  );
}
