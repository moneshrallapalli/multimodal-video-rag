import type { Metadata } from "next";

import { AdminConsole } from "@/components/admin/admin-console";

export const metadata: Metadata = { title: "Admin" };

export default function AdminPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6 sm:py-10">
      <h1 className="text-2xl font-semibold tracking-tight">Admin console</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Submit YouTube talks for ingestion and track job status. Admin-only — the public
        surface can only search the already-indexed library.
      </p>
      <div className="mt-6">
        <AdminConsole />
      </div>
    </div>
  );
}
