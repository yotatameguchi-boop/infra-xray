# Daily review / v0.2

## CLI

```bash
infra-xray review plan.json --format markdown --output report.md
infra-xray review plan.json --format json --output report.json
infra-xray review plan.json --format html --output report.html
infra-xray review plan.json --target production --commit FULL_COMMIT_SHA \
  --pr 123 --run-id 456 --config examples/review-config.json \
  --baseline previous-report.json --format html --output review.html
```

`FULL_COMMIT_SHA`は実際の完全なSHAに置き換えます。メタデータは任意ですが、PR投稿時は対象PR・SHA・run IDとの一致が必須です。入力・設定・比較元のファイルを出力先にすると拒否します。出力は一時ファイルから原子的に置き換えます。

HTMLにはUIとサニタイズ済みレビュー結果が含まれ、`file://`でオフライン閲覧できます。元のplan、変数、outputs等は含みません。構成情報自体は機密になり得るため、共有範囲は別途確認してください。

終了コードは `0`（解析成功・失敗条件なし）、`1`（解析成功・ポリシー違反）、`2`（解析・設定・出力エラー）。コード1でもレポートは生成されます。既存のview / checkの終了コード・JSON構造は変更していません。

## 設定

設定はJSONです。初期設定では全3ルールを評価しますが、警告の存在だけでは失敗にしません。[設定例](../examples/review-config.json)をコピーして利用してください。

```json
{
  "schema_version": 1,
  "enabled_rules": ["SG-001", "DB-001", "OPS-001"],
  "fail_on_rules": ["OPS-001"],
  "fail_on_severities": ["high"],
  "only_new": true,
  "fail_on_unknown": true,
  "suppressions": [
    {
      "rule_id": "DB-001",
      "resource": "aws_db_instance.primary",
      "reason": "一時的な検証環境としてレビュー済み。期限までに再確認する。",
      "expires": "2026-11-01"
    }
  ]
}
```

- ルールIDと重要度の失敗条件はORで評価します。
- `only_new`は警告に適用します。`fail_on_unknown`は別条件です。
- 初回の警告はNewです。比較元の形式・対象・ルールが互換でない場合はUncomparedとなり、only_newでも該当警告を保守的に失敗対象とします。
- 抑制は完全一致アドレス・理由・期限が必須です。UTCの日付で期限当日末まで有効。期限切れの場合は診断が復帰します。
- 抑制は安全確認や解消を意味しません。結果・理由・期限はレポートに残ります。
- 未対応キー、重複ルール、重複抑制、不正な期限、ワイルドカード抑制はエラーです。
- `max_input_bytes`（初期50 MiB）と`max_output_bytes`（初期10 MiB）は1 KiB〜100 MiB。設定ファイルは1 MiBまで。
- Markdownは60,000 bytes、コメントはさらに小さい要約に制限し、省略を明示します。完全なJSON / HTMLは指定上限を超えた場合にエラーになります。

## 前回比較

JSONレポートはschema_version=1です。対象名、PR番号、ルールエンジンの識別情報、有効なルール一覧が一致する結果を比較できます。失敗条件や抑制設定だけを変更した場合は比較可能です。

- New：今回新たに検出。
- Existing：前回から継続。
- Resolved：今回は同じルールを評価し、非該当と確認できた。
- Not evaluated：対象消失、対象外、未確定などで評価できない。
- Uncompared：互換性のある比較元が得られない。

ルール無効化では比較を互換とみなさず、解消を報告しません。リソース消失・unknown・抑制も解消扱いしません。過去レポートの属性値や診断文章は再配信せず、識別情報だけを比較に利用します。

GitHub連携は同じworkflow・同じPR・同じtargetの古い完了runから、互換性のある直近の解析成功結果を探します。ポリシー違反でジョブが失敗した結果も対象です。期限切れ・取得不可・不正なartifactはスキップし、比較不能を明示して解析を継続します。検索上限はworkflow runs 500件、各API一覧2,000件です。

## GitHub Actions：解析

Python 3.9以上のあるLinux runnerが必要です。Terraformの実行とplan生成は利用者側のCIで行います。以下のステップを、そのplanが存在するジョブへ追加します。

```yaml
permissions:
  contents: read
  actions: read
steps:
  # 利用者側のcheckoutとplan生成をここより前に配置
  - uses: yotatameguchi-boop/infra-xray/actions/review@v0.2.0
    id: review
    with:
      plan-path: plan.json
      target: production
      config-path: .infra-xray.json
      retention-days: '14'
```

実運用ではActionの参照をレビューしたコミットSHAへ固定してください。設定ファイルがない場合はconfig-pathを省略します。基準取得を行わない場合は `baseline: 'false'`、read-tokenを空にできます。

このActionはコメントを投稿しません。解析処理にAWS認証情報は不要です。解析はCI環境で行われ、サニタイズ済みレポートのみGitHub artifactへ保存されます。「端末からデータが出ない」機能ではありません。raw planを別ステップで誤ってuploadしないでください。

出力は `artifact-name` と `exit-code`。artifact名はtargetのSHA256先頭20文字を使用します。同一run内のtargetは一意にしてください。同一targetの重複並列ジョブはサポートしません。複数planはmatrixでtargetを分けます。

解析後にJSON・Markdown・HTMLだけをuploadし、その後にポリシーの終了コードを反映します。HTML等の生成が途中で失敗しても、既に生成できたレポートはuploadを試みます。解析自体が失敗した場合は成功レポートを偽造しません。

## GitHub Actions：コメント投稿（明示的に有効化）

書き込み権限のある別ジョブで実行します。解析ジョブに `issues: write` を付けないでください。例の `review` jobが単一targetの場合：

```yaml
publish:
  needs: review
  if: >-
    always() && needs.review.outputs.artifact-name != '' &&
    github.event_name == 'pull_request' &&
    github.event.pull_request.head.repo.full_name == github.repository
  runs-on: ubuntu-latest
  permissions:
    actions: read
    issues: write
  concurrency:
    group: infra-xray-comment-${{ github.repository }}-${{ github.event.pull_request.number }}-production
    cancel-in-progress: false
  steps:
    - uses: actions/download-artifact@v4
      with:
        name: ${{ needs.review.outputs.artifact-name }}
        path: review-result
    - uses: yotatameguchi-boop/infra-xray/actions/publish@v0.2.0
      with:
        report-path: review-result/report.json
        target: production
        post-comment: 'true'
        include-details: 'false'
        required: 'false'
```

解析job側のoutputsへ `artifact-name: ${{ steps.review.outputs.artifact-name }}` を追加します。複数planの実例は[人工planのworkflow](../.github/workflows/review-example.yml)を参照してください。このリポジトリの例では変数 `INFRA_XRAY_POST_COMMENTS=true` を設定したときだけ投稿ジョブが動き、初期状態は無効です。

投稿用Actionの参照は、解析側と同様に信頼済みSHAに固定します。書き込みジョブでPRのコード、Terraform、スクリプトを実行しないでください。外部forkには書き込みジョブを実行せず、Action自身もforkへの投稿を拒否します。`pull_request_target`による未信頼コードの実行は使用しません。

コメントはPR・targetごとのマーカーとBot作者IDで特定します。人のコメントは変更しません。初期表示は件数・SHA・runへのリンクのみで、属性値・リソースアドレスは掲載しません。詳細の掲載は `include-details: 'true'` で明示的に有効化します。

投稿必須でない場合のAPI障害は警告に留め、レポートを保持します。必須の場合は投稿jobが失敗します。古いSHA、閉じたPR、既に新しいrunのコメントがある場合は投稿を省略します。APIの読み取りとPATCHは上限付きで再試行し、POSTは通信結果が不明なときに二重投稿しないよう自動再試行しません。

同じPR・targetの投稿jobを必ずconcurrencyで直列化してください。投稿直前にもPR headを再確認しますが、GitHub APIのhead確認とコメント更新は単一トランザクションではありません。常に表示された対象SHAを確認してください。

チェックをマージ条件にする場合は、利用者がGitHubのブランチ保護で解析jobを必須チェックに設定します。

## 保護と制限

HTMLはReactのエスケープ、JSONのscript終端エスケープ、CSPを使用し、外部ネットワークアクセスを禁止しています。オフラインHTML自身をネットワークへ公開する機能はありません。

GitHub artifactを取得するときは、APIの認証情報を署名付きダウンロード先に引き継ぎません。取得サイズとZIP内のJSONサイズを制限し、APIが返すdigestがある場合は検証します。ZIPの任意パスを展開しません。取得した内容を実行しません。

v0.2はGitHub.com / GitHub Actionsの標準Botトークンを対象とします。GitHub Enterprise Server・カスタムGitHub App・PATによる投稿は対象外です。独自SaaS、ユーザー管理、課金、他のIaCツール対応は含みません。
