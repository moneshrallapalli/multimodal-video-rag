import { Badge } from "@/components/ui/badge";
import type { JobStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

const STYLES: Record<JobStatus, string> = {
  queued: "bg-muted text-muted-foreground",
  downloading: "bg-primary/10 text-primary",
  transcribing: "bg-primary/10 text-primary",
  embedding: "bg-primary/10 text-primary",
  completed: "bg-primary text-primary-foreground",
  failed: "bg-red-100 text-red-700",
};

export function JobStatusBadge({ status }: { status: JobStatus }) {
  return (
    <Badge variant="secondary" className={cn("capitalize", STYLES[status])}>
      {status}
    </Badge>
  );
}
