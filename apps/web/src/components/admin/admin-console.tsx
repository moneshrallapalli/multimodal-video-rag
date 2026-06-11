"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";
import type { IngestRequest, Job } from "@/lib/types";

import { AdminLogin } from "./admin-login";
import { IngestForm } from "./ingest-form";
import { JobsTable } from "./jobs-table";

export function AdminConsole() {
  const [authed, setAuthed] = useState<boolean | null>(null); // null = checking
  const [jobs, setJobs] = useState<Job[]>([]);

  useEffect(() => {
    api
      .session()
      .then((s) => setAuthed(s.authenticated))
      .catch(() => setAuthed(false));
  }, []);

  const refreshJobs = useCallback(async () => {
    try {
      const r = await api.jobs();
      setJobs(r.jobs);
    } catch {
      // a 401 here means the session lapsed; fall back to the login screen
      setAuthed(false);
    }
  }, []);

  useEffect(() => {
    if (!authed) return;
    // Fetch immediately (next tick) and then poll; both run as timer callbacks so
    // state is only updated from a subscription, not synchronously in the effect body.
    const initial = setTimeout(refreshJobs, 0);
    const id = setInterval(refreshJobs, 5000);
    return () => {
      clearTimeout(initial);
      clearInterval(id);
    };
  }, [authed, refreshJobs]);

  async function handleLogin(password: string) {
    try {
      await api.login(password);
      setAuthed(true);
      toast.success("Signed in");
    } catch (e) {
      toast.error(
        e instanceof ApiError && e.status === 401 ? "Incorrect password" : "Login failed",
      );
    }
  }

  async function handleLogout() {
    try {
      await api.logout();
    } finally {
      setAuthed(false);
      setJobs([]);
    }
  }

  async function handleIngest(req: IngestRequest) {
    try {
      const r = await api.ingest(req);
      setJobs((prev) => [r.job, ...prev]);
      toast.success("Job queued");
    } catch {
      toast.error("Could not queue the job");
    }
  }

  if (authed === null) {
    return <p className="text-sm text-muted-foreground">Checking session…</p>;
  }
  if (!authed) {
    return <AdminLogin onLogin={handleLogin} />;
  }

  return (
    <div className="animate-in fade-in flex flex-col gap-6 duration-300 ease-out">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">Signed in as admin.</p>
        <Button variant="outline" size="sm" onClick={handleLogout}>
          Sign out
        </Button>
      </div>
      <IngestForm onSubmit={handleIngest} />
      <JobsTable jobs={jobs} />
    </div>
  );
}
