import { describe, it, expect } from "vitest";
import { layout } from "./graph";
import type { Graph, Resource } from "./types";
const node = (id: string): Resource => ({
  id,
  name: id,
  type: "aws_instance",
  action: "create",
  before: {},
  after: {},
  findings: [],
  limitations: [],
});
const graph: Graph = {
  schemaVersion: 1,
  terraformVersion: "1.9.8",
  formatVersion: "1.2",
  nodes: [node("aws_instance.a"), node("aws_instance.b")],
  edges: [
    {
      id: "ab",
      source: "aws_instance.a",
      target: "aws_instance.b",
      kind: "reference",
      label: "Terraform reference",
      evidence: "configuration",
    },
  ],
  findings: [],
  limitations: [],
  ignoredResources: 0,
};
describe("graph layout", () => {
  it("preserves reference topology while changing view", () => {
    for (const mode of ["architecture", "change", "security"] as const) {
      const result = layout(graph, mode, "");
      expect(result.edges).toHaveLength(1);
      expect(result.nodes[0].position.y).toBeLessThan(
        result.nodes[1].position.y,
      );
      expect(result.nodes[0].data.mode).toBe(mode);
    }
  });
  it("filters nodes and dangling edges", () => {
    const result = layout(graph, "architecture", "instance.a");
    expect(result.nodes).toHaveLength(1);
    expect(result.edges).toHaveLength(0);
  });
  it("accepts empty and 100-resource graphs", () => {
    expect(
      layout({ ...graph, nodes: [], edges: [] }, "architecture", "").nodes,
    ).toHaveLength(0);
    const r = layout(
      {
        ...graph,
        nodes: Array.from({ length: 100 }, (_, i) => node("node" + i)),
        edges: [],
      },
      "architecture",
      "",
    );
    expect(r.nodes).toHaveLength(100);
    expect(r.nodes.every((n) => Number.isFinite(n.position.x))).toBe(true);
  });
});
