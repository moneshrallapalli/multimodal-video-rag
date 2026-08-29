export type CockpitTint = "blue" | "gold" | "purple" | "red";
export type CockpitStatus =
  | "idle"
  | "started"
  | "ok"
  | "skipped"
  | "retry"
  | "failed"
  | "refused";

export interface CockpitDisplayNode<Id extends string = string> {
  id: Id;
  label: string;
  detail: string;
}

export interface CockpitColumn<Id extends string = string> {
  id: string;
  label: string;
  tint: CockpitTint;
  nodes: CockpitDisplayNode<Id>[];
}

export interface CockpitRuntime {
  status: CockpitStatus;
  metric: string;
}
