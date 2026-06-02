import { Eye, MessageSquareText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { Modality } from "@/lib/types";
import { cn } from "@/lib/utils";

export function ModalityBadge({
  modality,
  className,
}: {
  modality: Modality;
  className?: string;
}) {
  const isVisual = modality === "visual";
  const Icon = isVisual ? Eye : MessageSquareText;
  return (
    <Badge
      variant="secondary"
      className={cn("gap-1 font-medium", isVisual && "bg-primary/10 text-primary", className)}
    >
      <Icon className="size-3" />
      {isVisual ? "Visual" : "Transcript"}
    </Badge>
  );
}
