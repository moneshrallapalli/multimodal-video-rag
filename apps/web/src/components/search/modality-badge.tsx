import { Eye, ImageIcon, MessageSquareText } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { Modality } from "@/lib/types";
import { cn } from "@/lib/utils";

const CONFIG: Record<Modality, { label: string; icon: typeof Eye; accent: boolean }> = {
  visual: { label: "Visual", icon: Eye, accent: true },
  visual_caption: { label: "Frame caption", icon: ImageIcon, accent: true },
  transcript: { label: "Transcript", icon: MessageSquareText, accent: false },
};

export function ModalityBadge({
  modality,
  className,
}: {
  modality: Modality;
  className?: string;
}) {
  const { label, icon: Icon, accent } = CONFIG[modality];
  return (
    <Badge
      variant="secondary"
      className={cn("gap-1 font-medium", accent && "bg-primary/10 text-primary", className)}
    >
      <Icon className="size-3" />
      {label}
    </Badge>
  );
}
