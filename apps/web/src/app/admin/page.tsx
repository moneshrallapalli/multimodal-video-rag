import type { Metadata } from "next";

import { AdminConsole } from "@/components/admin/admin-console";

export const metadata: Metadata = { title: "Admin" };

export default function AdminPage() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10">
      <section className="mb-8 rounded-2xl border border-border/80 bg-card/70 p-6 shadow-sm backdrop-blur-sm sm:p-8">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Admin console</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Queue a YouTube talk and watch the worker path: download, frames, Whisper,
          Titan embeddings, and Pinecone upsert. The public search surface only sees
          videos that finish this graph.
        </p>
      </section>
      <AdminConsole />
    </div>
  );
}
