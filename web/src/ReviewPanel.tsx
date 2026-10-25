import React from "react";
import type { Review } from "./types";
export function ReviewPanel({
  review,
  select,
}: {
  review: Review;
  select: (id: string) => void;
}) {
  const unknown = review.evaluations.filter((e) => e.status === "unknown");
  return (
    <section className="review-context" aria-label="レビューサマリー">
      <div className="review-title">
        <strong>Review · {review.target}</strong>
        <span className={review.check.exit_code ? "risk" : "create"}>
          {review.check.status === "passed"
            ? "✓ 失敗条件に該当しない"
            : "△ 設定された失敗条件に該当"}
        </span>
      </div>
      <div className="review-meta">
        <span>
          Commit <code>{review.commit || "未指定"}</code>
        </span>
        <span>
          PR #{review.pr ?? "—"} · Run {review.run_id ?? "—"}
        </span>
        <span>{review.analyzed_at}</span>
        <span>
          Infra X-Ray {review.tool_version} · schema {review.schema_version}
        </span>
      </div>
      <p>{review.comparison.message}</p>
      <div className="review-counts">
        <span>
          New <b>{review.summary.new}</b>
        </span>
        <span>
          抑制済み <b>{review.summary.suppressed}</b>
        </span>
        <span>
          判定不能 <b>{review.summary.unknown}</b>
        </span>
        <span>
          対象外リソース <b>{review.summary.ignored_resources}</b>
        </span>
      </div>
      <details>
        <summary>前回レビューとの比較・判定不能・設定情報</summary>
        <p>
          前回Commit: <code>{review.comparison.baseline_commit || "—"}</code>
        </p>
        <p>
          Rules: {review.enabled_rules.join(" / ")}
          <br />
          Config: <code>{review.config_fingerprint}</code>
        </p>
        {review.historical.map((f) => (
          <div className="history-row" key={f.key}>
            <strong>
              {f.comparison} · {f.id}
            </strong>
            <code>{f.resource}</code>
            <p>{f.reason}</p>
          </div>
        ))}
        {unknown.map((e) => (
          <button
            className="history-row"
            key={e.key}
            onClick={() => select(e.resource)}
          >
            <strong>Not evaluated · {e.id}</strong>
            <code>{e.resource}</code>
            <span>{e.reason}</span>
          </button>
        ))}
        {!review.historical.length && !unknown.length && (
          <p>履歴上の解消事項・判定不能事項はありません。</p>
        )}
      </details>
      <small>
        警告なしは安全性の保証ではありません。構成情報を含むため、レポートの公開範囲を確認してください。
      </small>
    </section>
  );
}
