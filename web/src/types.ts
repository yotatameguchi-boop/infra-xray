export type Action =
  "create" | "update" | "delete" | "replace" | "no-change" | "read";
export type Mode = "architecture" | "change" | "security";
export type Finding = {
  id: string;
  resource: string;
  title: string;
  reason: string;
  evidence: string;
  severity: string;
  limitations: string;
};
export type Resource = {
  id: string;
  name: string;
  type: string;
  action: Action;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  findings: Finding[];
  limitations: string[];
};
export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  kind: string;
  label: string;
  evidence: string;
};
export type Graph = {
  schemaVersion: number;
  terraformVersion: string;
  formatVersion: string;
  nodes: Resource[];
  edges: GraphEdge[];
  findings: Finding[];
  limitations: string[];
  ignoredResources: number;
};
