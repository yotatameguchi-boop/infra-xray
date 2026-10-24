import dagre from "@dagrejs/dagre";
import type { Graph, Mode } from "./types";
export const labels = {
  create: "+ Create",
  update: "↗ Update",
  delete: "− Delete",
  replace: "⇄ Replace",
  "no-change": "○ No change",
  read: "◇ Read",
};
export function layout(graph: Graph, mode: Mode, query: string) {
  const visible = graph.nodes.filter((n) =>
    `${n.id} ${n.type}`.toLowerCase().includes(query.toLowerCase()),
  );
  const ids = new Set(visible.map((n) => n.id));
  const edges = graph.edges.filter(
    (e) => ids.has(e.source) && ids.has(e.target),
  );
  const g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir: "TB",
    nodesep: 42,
    ranksep: 85,
    marginx: 32,
    marginy: 32,
  });
  g.setDefaultEdgeLabel(() => ({}));
  visible.forEach((n) => g.setNode(n.id, { width: 230, height: 96 }));
  edges.forEach((e) => g.setEdge(e.source, e.target));
  dagre.layout(g);
  return {
    nodes: visible.map((n) => ({
      id: n.id,
      type: "resource",
      position: { x: g.node(n.id).x - 115, y: g.node(n.id).y - 48 },
      data: { resource: n, mode },
    })),
    edges: edges.map((e) => ({
      ...e,
      type: "smoothstep",
      animated: false,
      style: { stroke: "#394757", strokeWidth: 1.5 },
    })),
  };
}
