// @vitest-environment jsdom
import React from "react";
import { afterEach, beforeEach, describe, it, expect, vi } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { ReactFlowProvider } from "@xyflow/react";
import { App } from "./App";
import type { Graph } from "./types";
const finding = {
  id: "DB-001",
  resource: "aws_db_instance.primary",
  title: "RDSのパブリックアクセスが有効化",
  reason: "公開設定を確認",
  evidence: "false → true",
  severity: "high",
  limitations: "到達性は未評価",
};
const graph: Graph = {
  schemaVersion: 1,
  terraformVersion: "1.9.8",
  formatVersion: "1.2",
  nodes: [
    {
      id: "aws_db_instance.primary",
      name: "primary",
      type: "aws_db_instance",
      action: "replace",
      before: { publicly_accessible: false },
      after: { publicly_accessible: true },
      findings: [finding],
      limitations: [],
    },
  ],
  edges: [],
  findings: [finding],
  limitations: ["限定的な診断です"],
  ignoredResources: 0,
};
beforeEach(() => {
  window.history.replaceState(null, "", "/#token=test-token");
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => graph }),
  );
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
  vi.stubGlobal(
    "DOMMatrixReadOnly",
    class {
      m22 = 1;
    },
  );
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});
const mount = () =>
  render(
    <ReactFlowProvider>
      <App />
    </ReactFlowProvider>,
  );
describe("explorer interface", () => {
  it("loads token-protected graph and switches views", async () => {
    mount();
    await screen.findByText("Infrastructure explorer");
    expect(fetch).toHaveBeenCalledWith("/api/graph", {
      headers: { Authorization: "Bearer test-token" },
    });
    expect(window.location.hash).toBe("");
    expect(sessionStorage.getItem("infra-xray-token")).toBe("test-token");
    fireEvent.click(screen.getByRole("tab", { name: "Changes" }));
    expect(
      screen
        .getByRole("tab", { name: "Changes" })
        .getAttribute("aria-selected"),
    ).toBe("true");
    fireEvent.click(screen.getByRole("tab", { name: /Security/ }));
    expect(
      screen
        .getByRole("tab", { name: /Security/ })
        .getAttribute("aria-selected"),
    ).toBe("true");
  });
  it("opens findings, evidence, and limited attributes, then searches", async () => {
    const view = mount();
    await screen.findByText("Infrastructure explorer");
    fireEvent.click(view.container.querySelector(".finding-row")!);
    expect(view.container.querySelector(".details h2")?.textContent).toBe(
      "primary",
    );
    expect(view.container.querySelector(".details")?.textContent).toContain(
      "false → true",
    );
    expect(
      view.container.querySelector(".details .badge")?.textContent,
    ).toContain("Replace");
    fireEvent.click(screen.getByLabelText("詳細を閉じる"));
    expect(screen.getByText("A closer look")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("リソース検索"), {
      target: { value: "nonexistent" },
    });
    expect(screen.getByText("一致するリソースがありません")).toBeTruthy();
    fireEvent.click(screen.getByLabelText("検索をクリア"));
    expect(
      (screen.getByLabelText("リソース検索") as HTMLInputElement).value,
    ).toBe("");
    fireEvent.click(screen.getByRole("button", { name: "診断の範囲と限界" }));
    expect(screen.getByText("限定的な診断です")).toBeTruthy();
  });
  it("shows an actionable API failure without fabricating data", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    mount();
    expect((await screen.findByRole("alert")).textContent).toContain("CLI");
    expect(screen.queryByRole("tab")).toBeNull();
  });
});
