"use client";

import { LoaderCircle, Lock } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function AdminLogin({ onLogin }: { onLogin: (password: string) => Promise<void> }) {
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!password) return;
    setBusy(true);
    try {
      await onLogin(password);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="animate-in fade-in slide-in-from-bottom-2 max-w-sm duration-300 ease-out">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Lock className="size-4 text-primary" /> Admin sign in
        </CardTitle>
        <CardDescription>Enter the admin password to manage ingestion.</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
          className="flex flex-col gap-3"
        >
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="admin-password">Password</Label>
            <Input
              id="admin-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              placeholder="••••••••"
            />
          </div>
          <Button type="submit" disabled={busy || !password}>
            {busy && <LoaderCircle className="size-4 animate-spin" aria-hidden />}
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
