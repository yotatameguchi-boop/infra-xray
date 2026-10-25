import React, { useEffect, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  ReactFlowProvider,
  useReactFlow,
  type NodeProps,
  type Node,
  type NodeTypes,
} from "@xyflow/react";
import {
  Activity,
  Box,
  Boxes,
  Network,
  Server,
  Database,
  Shield,
  GitBranch,
  Search,
  ArrowUpRight,
  LockKeyhole,
  ChevronRight,
  CircleAlert,
  X,
  Maximize,
  Layers,
  Workflow,
  CircleHelp,
  Terminal,
} from "lucide-react";
import { ReviewPanel } from "./ReviewPanel";
import type { Graph, Resource, Mode, Review } from "./types";
import { layout, labels } from "./graph";
import "@xyflow/react/dist/style.css";
import "./styles.css";
const icons: Record<string, typeof Box> = {
  aws_instance: Server,
  aws_db_instance: Database,
  aws_vpc: Network,
  aws_subnet: Boxes,
  aws_security_group: Shield,
  aws_vpc_security_group_ingress_rule: Shield,
  aws_lb: Workflow,
};
const names: Record<string, string> = {
  aws_instance: "EC2 INSTANCE",
  aws_db_instance: "RDS DATABASE",
  aws_vpc: "VPC",
  aws_subnet: "SUBNET",
  aws_security_group: "SECURITY GROUP",
  aws_vpc_security_group_ingress_rule: "INGRESS RULE",
  aws_lb: "LOAD BALANCER",
};
function ResourceNode({
  data,
  selected,
}: NodeProps<Node<{ resource: Resource; mode: Mode }>>) {
  const r = data.resource,
    Icon = icons[r.type] || Box;
  const accent =
    data.mode === "security"
      ? r.findings.length
        ? "risk"
        : "muted"
      : data.mode === "change"
        ? r.action
        : "architecture";
  return (
    <div className={`resource-node ${accent} ${selected ? "selected" : ""}`}>
      <Handle type="target" position={Position.Top} />
      <div className="node-top">
        <span className="resource-icon">
          <Icon size={19} />
        </span>
        <span className="node-kind">{names[r.type] || r.type}</span>
        {r.findings.length > 0 && (
          <span className="node-alert">
            <CircleAlert size={13} />
            {r.findings.length}
          </span>
        )}
      </div>
      <div className="node-name" title={r.id}>
        {r.name}
      </div>
      <div className={`node-action ${r.action}`}>{labels[r.action]}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
const nodeTypes: NodeTypes = { resource: ResourceNode };
export function App() {
  const [graph, setGraph] = useState<Graph | null>(null),
    [review, setReview] = useState<Review | null>(null),
    [error, setError] = useState(""),
    [mode, setMode] = useState<Mode>("architecture"),
    [selected, setSelected] = useState<string | null>(null),
    [query, setQuery] = useState(""),
    [help, setHelp] = useState(false);
  const flow = useReactFlow();
  useEffect(() => {
    const embedded = document.getElementById("infra-xray-review");
    if (embedded) {
      try {
        const value = JSON.parse(embedded.textContent || "");
        if (value.schema_version !== 1 || !value.graph) throw new Error();
        setReview(value);
        setGraph(value.graph);
      } catch {
        setError("レポートの形式を確認してください。");
      }
      return;
    }
    const token = new URLSearchParams(location.hash.slice(1)).get("token");
    if (token) sessionStorage.setItem("infra-xray-token", token);
    history.replaceState(null, "", location.pathname);
    fetch("/api/graph", {
      headers: {
        Authorization: `Bearer ${token || sessionStorage.getItem("infra-xray-token") || ""}`,
      },
    })
      .then((r) => {
        if (!r.ok)
          throw new Error(
            "解析データを読み込めません。CLIが表示したURLから開き直してください。",
          );
        return r.json();
      })
      .then(setGraph)
      .catch((e) => setError(e.message));
  }, []);
  const result = useMemo(
    () => (graph ? layout(graph, mode, query) : { nodes: [], edges: [] }),
    [graph, mode, query],
  );
  const resource = graph?.nodes.find((n) => n.id === selected);
  useEffect(() => {
    const id = setTimeout(
      () => flow.fitView({ padding: 0.22, duration: 300 }),
      80,
    );
    return () => clearTimeout(id);
  }, [query, graph, flow]);
  function select(id: string) {
    setSelected(id);
    const node = flow.getNode(id);
    if (node)
      flow.fitView({
        nodes: [node],
        maxZoom: 1.1,
        duration: 400,
        padding: 1.2,
      });
  }
  if (error)
    return (
      <main className="loading">
        <CircleAlert />
        <h1>読み込みに失敗しました</h1>
        <p role="alert">{error}</p>
        <code>infra-xray view plan.json</code>
      </main>
    );
  if (!graph)
    return (
      <main className="loading">
        <Activity className="pulse" />
        <h1>Reading your infrastructure…</h1>
        <p>ローカルの解析結果を読み込んでいます</p>
      </main>
    );
  const changed = graph.nodes.filter((n) => n.action !== "no-change").length;
  return (
    <div className="app">
      <aside className="rail">
        <div className="brand-icon">
          <Activity size={23} />
        </div>
        <button
          aria-label="構成表示"
          title="構成表示"
          className={mode === "architecture" ? "active" : ""}
          onClick={() => setMode("architecture")}
        >
          <Boxes />
        </button>
        <button
          aria-label="変更表示"
          title="変更表示"
          className={mode === "change" ? "active" : ""}
          onClick={() => setMode("change")}
        >
          <GitBranch />
        </button>
        <button
          aria-label="セキュリティ表示"
          title="セキュリティ表示"
          className={mode === "security" ? "active" : ""}
          onClick={() => setMode("security")}
        >
          <Shield />
        </button>
        <button
          className="rail-help"
          aria-label="診断の範囲"
          onClick={() => setHelp(!help)}
        >
          <CircleHelp />
        </button>
        <span className="version">0.2</span>
      </aside>
      <div className="workspace">
        <header>
          <div>
            <div className="brand">
              Infra <strong>X-Ray</strong>
              <span className="preview">LOCAL PREVIEW</span>
            </div>
            <p>See what your infrastructure is becoming.</p>
          </div>
          <div className="environment">
            <span className="status-dot" />{" "}
            {review ? "Offline review" : "Local environment"}{" "}
            <span className="divider" />
            <LockKeyhole size={13} />{" "}
            {review ? "Self-contained report" : "Private by design"}
          </div>
        </header>
        <section className="page-title">
          <div className="eyebrow">
            WORKSPACE <ChevronRight size={12} /> TERRAFORM PLAN
          </div>
          <div className="title-row">
            <div>
              <h1>
                Infrastructure explorer<span className="title-dot">.</span>
              </h1>
              <p>構成を見渡し、変更を理解する。</p>
            </div>
            <span className="terraform">
              <Layers size={16} /> Terraform {graph.terraformVersion}
            </span>
          </div>
        </section>
        <section className="metrics">
          <div>
            <span className="metric-icon">
              <Boxes />
            </span>
            <span>
              <small>RESOURCES</small>
              <b>
                {graph.nodes.length}
                <em>managed resources</em>
              </b>
            </span>
          </div>
          <div>
            <span className="metric-icon blue">
              <GitBranch />
            </span>
            <span>
              <small>PLANNED CHANGES</small>
              <b>
                {changed}
                <em>changes to review</em>
              </b>
            </span>
          </div>
          <div>
            <span className="metric-icon amber">
              <Shield />
            </span>
            <span>
              <small>REVIEW FINDINGS</small>
              <b>
                {graph.findings.length}
                <em>items need attention</em>
              </b>
            </span>
          </div>
          <div className="privacy-card">
            <LockKeyhole size={19} />
            <span>
              {review
                ? "構成情報を含むレビュー結果"
                : "データはこのマシンの中だけに"}
              <small>
                {review
                  ? "OFFLINE REPORT · CHECK SHARING SCOPE"
                  : "LOCAL ANALYSIS · NO UPLOADS"}
              </small>
            </span>
          </div>
        </section>
        {review && (
          <ReviewPanel
            review={review}
            select={(id) => {
              setQuery("");
              select(id);
            }}
          />
        )}
        <section className="explorer">
          <div className="toolbar">
            <div className="mode-tabs" role="tablist" aria-label="表示モード">
              {(
                [
                  ["architecture", "Architecture", Network],
                  ["change", "Changes", GitBranch],
                  ["security", "Security", Shield],
                ] as const
              ).map(([key, label, Icon]) => (
                <button
                  role="tab"
                  aria-selected={mode === key}
                  key={key}
                  onClick={() => setMode(key)}
                  className={mode === key ? "active" : ""}
                >
                  <Icon size={15} />
                  {label}
                  {key === "security" && <span>{graph.findings.length}</span>}
                </button>
              ))}
            </div>
            <label className="search">
              <Search size={15} />
              <input
                aria-label="リソース検索"
                placeholder="Find a resource…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              {query && (
                <button aria-label="検索をクリア" onClick={() => setQuery("")}>
                  <X size={13} />
                </button>
              )}
            </label>
            <button
              className="fit"
              title="グラフ全体を表示"
              aria-label="グラフ全体を表示"
              onClick={() => flow.fitView({ padding: 0.2, duration: 300 })}
            >
              <Maximize size={17} />
            </button>
          </div>
          <div className="graph-body">
            <div className="canvas">
              <div className="canvas-caption">
                <span className="status-dot" />
                {mode === "architecture"
                  ? "RESOURCE TOPOLOGY"
                  : mode === "change"
                    ? "PLANNED CHANGES"
                    : "SECURITY REVIEW"}
                <span>
                  {result.nodes.length} resources · {result.edges.length}{" "}
                  references
                </span>
              </div>
              <ReactFlow
                nodes={result.nodes.map((n) => ({
                  ...n,
                  selected: n.id === selected,
                }))}
                edges={result.edges}
                onNodesChange={(changes) => {
                  const picked = changes.find(
                    (c) => c.type === "select" && c.selected,
                  );
                  if (picked && picked.type === "select")
                    setSelected(picked.id);
                  else if (
                    changes.some(
                      (c) =>
                        c.type === "select" && c.id === selected && !c.selected,
                    )
                  )
                    setSelected(null);
                }}
                nodeTypes={nodeTypes}
                onNodeClick={(_, n) => setSelected(n.id)}
                onPaneClick={() => setSelected(null)}
                nodesDraggable={false}
                nodesConnectable={false}
                deleteKeyCode={null}
                fitView
                minZoom={0.15}
                maxZoom={2}
                colorMode="dark"
              >
                <Background color="#27303e" gap={22} size={1} />
                <Controls showInteractive={false} />
                <MiniMap
                  nodeColor="#33465a"
                  maskColor="rgba(10,16,24,.75)"
                  pannable
                  zoomable
                />
              </ReactFlow>
              {!result.nodes.length && (
                <div className="empty-graph">
                  <Search />
                  <h3>
                    {query
                      ? "一致するリソースがありません"
                      : "対応リソースがありません"}
                  </h3>
                  <p>検索条件またはplanファイルを確認してください。</p>
                </div>
              )}
              <div className="legend">
                {mode === "security" ? (
                  <>
                    <span className="risk">△ 要確認</span>
                    <span>○ 検出なし / 対象外</span>
                  </>
                ) : (
                  Object.entries(labels)
                    .filter(([k]) => k !== "read")
                    .map(([key, label]) => (
                      <span key={key} className={key}>
                        {label}
                      </span>
                    ))
                )}
              </div>
            </div>
            <aside className="details">
              <div className="panel-header">
                <span>RESOURCE DETAILS</span>
                {resource && (
                  <button
                    aria-label="詳細を閉じる"
                    onClick={() => setSelected(null)}
                  >
                    <X size={16} />
                  </button>
                )}
              </div>
              {resource ? (
                <>
                  <div className="detail-heading">
                    <span className="large-icon">
                      {React.createElement(icons[resource.type] || Box, {
                        size: 25,
                      })}
                    </span>
                    <span className={`badge ${resource.action}`}>
                      {labels[resource.action]}
                    </span>
                    <h2>{resource.name}</h2>
                    <p>{resource.type}</p>
                  </div>
                  <section className="detail-section">
                    <h3>TERRAFORM ADDRESS</h3>
                    <code>{resource.id}</code>
                  </section>
                  <section className="detail-section">
                    <h3>
                      ATTRIBUTE CHANGES <span>許可リスト</span>
                    </h3>
                    {[
                      ...new Set([
                        ...Object.keys(resource.before),
                        ...Object.keys(resource.after),
                      ]),
                    ].map((key) => (
                      <div className="attribute" key={key}>
                        <strong>{key}</strong>
                        <div>
                          <span className="before">
                            {JSON.stringify(resource.before[key] ?? "—")}
                          </span>
                          <ArrowUpRight size={12} />
                          <span className="after">
                            {JSON.stringify(resource.after[key] ?? "—")}
                          </span>
                        </div>
                      </div>
                    ))}
                    {!Object.keys(resource.before).length &&
                      !Object.keys(resource.after).length && (
                        <p>表示可能な属性はありません。</p>
                      )}
                  </section>
                  <section className="detail-section">
                    <h3>REFERENCES</h3>
                    {graph.edges
                      .filter(
                        (e) =>
                          e.source === resource.id || e.target === resource.id,
                      )
                      .map((e) => (
                        <button
                          className="reference"
                          key={e.id}
                          onClick={() =>
                            select(
                              e.source === resource.id ? e.target : e.source,
                            )
                          }
                        >
                          <GitBranch size={13} />
                          <span>
                            {e.source === resource.id ? e.target : e.source}
                            <small>{e.evidence}</small>
                          </span>
                        </button>
                      ))}
                    {!graph.edges.some(
                      (e) =>
                        e.source === resource.id || e.target === resource.id,
                    ) && <p>確認できた参照関係はありません。</p>}
                  </section>
                  <section className="detail-section">
                    <h3>SECURITY REVIEW</h3>
                    {resource.findings.map((f) => (
                      <div className="finding-detail" key={f.id}>
                        <b>
                          {f.id} · {f.title}
                        </b>
                        <p>{f.reason}</p>
                        <small>判定根拠</small>
                        <p>{f.evidence}</p>
                        <small>{f.limitations}</small>
                        {f.comparison && <p>比較: {f.comparison}</p>}
                        {f.suppression && (
                          <p className="limitation">
                            {f.suppressed ? "抑制済み" : "抑制期限切れ"}:{" "}
                            {f.suppression.reason} · {f.suppression.expires}{" "}
                            (UTC)
                          </p>
                        )}
                      </div>
                    ))}
                    {!resource.findings.length && (
                      <p>
                        このリソースで確認事項は検出されていません。安全性を保証するものではありません。
                      </p>
                    )}
                    {resource.limitations.map((l) => (
                      <p className="limitation" key={l}>
                        {l}
                      </p>
                    ))}
                  </section>
                </>
              ) : (
                <div className="detail-empty">
                  <div className="empty-symbol">
                    <Box size={32} />
                    <span>+</span>
                  </div>
                  <h3>A closer look</h3>
                  <p>
                    グラフのリソースを選択して、
                    <br />
                    変更内容と診断の根拠を確認。
                  </p>
                  <div className="hint">
                    <span>↖</span> Click a resource to inspect
                  </div>
                </div>
              )}
            </aside>
          </div>
          <div className="graph-footnote">
            <GitBranch size={12} />{" "}
            線はTerraformの参照関係です。実際のネットワーク通信経路ではありません。
            <span>SCROLL TO ZOOM · DRAG TO PAN</span>
          </div>
        </section>
        <section className="findings-panel">
          <div className="findings-heading">
            <h2>
              <Shield size={17} /> Review findings{" "}
              <span>{graph.findings.length}</span>
            </h2>
            <button onClick={() => setHelp(!help)}>
              診断の範囲と限界 <CircleHelp size={13} />
            </button>
          </div>
          {graph.findings.length ? (
            graph.findings.map((f) => (
              <button
                className="finding-row"
                key={f.id + f.resource}
                onClick={() => {
                  setMode("security");
                  setQuery("");
                  select(f.resource);
                }}
              >
                <span className={"severity " + f.severity}>
                  <CircleAlert size={15} />
                  {f.severity === "high" ? "HIGH" : "REVIEW"}
                </span>
                <span className="rule-id">{f.id}</span>
                <span className="finding-title">
                  {f.title}
                  <small>
                    {f.resource} {f.comparison && `· ${f.comparison}`}{" "}
                    {f.suppressed && "· Suppressed"}
                  </small>
                </span>
                <span className="review-link">
                  Inspect resource <ArrowUpRight size={15} />
                </span>
              </button>
            ))
          ) : (
            <div className="no-findings">
              <Shield size={18} />{" "}
              確認事項は検出されませんでした。診断対象は限定されています。
            </div>
          )}
          {graph.nodes.some((n) => n.limitations.length > 0) && (
            <div className="limits-summary">
              <CircleAlert size={14} />{" "}
              {graph.nodes.filter((n) => n.limitations.length > 0).length}
              リソースで判定できない属性があります。ノードの詳細を確認してください。
            </div>
          )}
        </section>
        {help && (
          <section className="help-panel">
            <h3>診断の範囲と限界</h3>
            {graph.limitations.map((l) => (
              <p key={l}>{l}</p>
            ))}
            <p>
              対象外リソース: {graph.ignoredResources} ·
              sensitive属性はマスクし、unknown属性は未確定として扱います。
            </p>
            <code>terraform show -json tfplan &gt; plan.json</code>
            <p>別のplanを表示する場合: infra-xray view plan.json</p>
          </section>
        )}
        <footer>
          <span>
            <Activity size={13} /> INFRA X-RAY <b>v0.2.0</b>
          </span>
          <span>
            Evidence, not assumptions.<span className="footer-dot">·</span>{" "}
            Built for local-first reviews
          </span>
        </footer>
      </div>
    </div>
  );
}
