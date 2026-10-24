# v0.1 検証記録

検証日: 2026-10-24（Asia/Tokyo）。環境: macOS 26.4.1 / arm64、Python 3.9.6、Node.js 24.18.1。

## 通過した検証

- Python / pytest: 55件。形式検証、7種のリソース、変更操作、3ルールの検出・非検出、unknown / sensitive / 不正なマスク、機密カナリアの非漏出、configuration参照、未対応リソース、100リソースの解析。
- サーバーのテスト: 上記55件に含む。トークン必須、Host検証、cross-site拒否、CSP、no-store、パストラバーサル拒否。
- Vitest: 6件。3表示モードのデータ、検索に伴うエッジ除去、100ノードのレイアウト、実際のReact UIをjsdomでマウントした表示切り替え・検索・診断詳細・APIエラー表示。
- TypeScript型チェックとVite本番ビルドに成功。React Flowの `use client` ディレクティブをViteが無視する非致命的な警告あり。
- 本番HTTP smoke check: HTML / JS / CSSの配信、およびトークン付きAPIで9リソース・3件の診断取得に成功。
- 100リソース解析50回: 中央値0.383 ms、最大1.336 ms。詳細は `parser-performance.json`。単一環境の参考計測であり性能保証ではありません。

ビルド済みwheelを新しい仮想環境にオフラインインストールし、`infra-xray --help` と `infra-xray check` を実行して成功を確認しました。wheelに現行のUIとサニタイザーが含まれることも検証済みです。

## GitHub Actionsでの追加検証

[初回の成功した実行](https://github.com/yotatameguchi-boop/infra-xray/actions/runs/40062527918)で、Ubuntu / Python 3.12 / Node.js 22 / Chromiumによる以下の検証が成功しました。

- Python 55件、Vitest 6件、Playwright E2E 2件。
- 表示モード、リソース詳細、検索、診断根拠、キーボード選択、モバイル幅、再読み込み。
- ページのJavaScript例外なし、外部へのページリクエストなし。
- 100リソースの描画。navigationから100ノードのDOMマウントまで217 ms（単一実行の参考値）。
- wheel / sdist / 実行用ZIPの生成と、インストール済みCLIによるsafeサンプルの解析。

実画面から生成したスクリーンショットを `docs/screenshots/desktop.png` と `docs/screenshots/mobile.png` に保存しました。動画はActionsの `browser-evidence` artifactに含まれます（保持期間14日）。再実行時の測定値は当該実行のartifactを参照してください。

```bash
cd web
npm ci
npm run build
npx playwright install chromium
npx playwright test
```

スクリーンショットは `docs/screenshots/`、動画は `web/test-results/`、表示時間は `docs/browser-performance.json` に出力されます。必要なら `CHROMIUM_PATH` で既存のブラウザー実行ファイルを指定できます。

## 未確認の項目

macOSローカルのサンドボックス内ではChromiumのMachPortRendezvous権限拒否があり、実ブラウザーの検証をGitHub Actions上のLinuxで実施しました。Windows / macOSの実ブラウザーCI、外部利用者による試用、大規模な実環境構成の性能検証は未実施です。
