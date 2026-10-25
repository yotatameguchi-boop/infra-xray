export type Action =
  "create" | "update" | "delete" | "replace" | "no-change" | "read";
export type Mode = "architecture" | "change" | "security";
export type Finding = {
  comparison?: string;
  suppressed?: boolean;
  suppression?: { reason: string; expires: string; expired: boolean } | null;
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
export type Review = {
  schema_version: number;
  tool_version: string;
  target: string;
  commit: string | null;
  pr: number | null;
  run_id: number | null;
  analyzed_at: string;
  config_fingerprint: string;
  enabled_rules: string[];
  summary: {
    findings: number;
    suppressed: number;
    unknown: number;
    ignored_resources: number;
    new: number;
  };
  check: { status: string; exit_code: number };
  comparison: {
    status: string;
    message: string;
    baseline_commit: string | null;
  };
  historical: {
    key: string;
    resource: string;
    id: string;
    comparison: string;
    reason: string;
  }[];
  evaluations: {
    key: string;
    resource: string;
    id: string;
    status: string;
    reason?: string;
  }[];
  graph: Graph;
};
