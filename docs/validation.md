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

## この環境で未確認の項目

Playwrightによる実ブラウザーE2Eを2件用意し実行しましたが、ChromeおよびChromium headless shellがテスト開始前にmacOSサンドボックスのMachPortRendezvous権限拒否で停止しました。UIの動作不具合による失敗とは判定していませんが、実ブラウザーの描画・操作が通過したとも主張していません。

このため、実ブラウザーの100ノード初期表示時間、スクリーンショットによる見た目の検証、デモ動画の生成は未完了です。ブラウザー起動可能な環境で以下を実行すると、E2E・スクリーンショット・動画・初期表示時間の記録を生成します。

```bash
cd web
npm ci
npm run build
npx playwright install chromium
npx playwright test
```

スクリーンショットは `docs/screenshots/`、動画は `web/test-results/`、表示時間は `docs/browser-performance.json` に出力されます。必要なら `CHROMIUM_PATH` で既存のブラウザー実行ファイルを指定できます。

GitHub Actionsの設定ファイルは同梱していますが、リモート上の実行はまだありません。GitHub公開、外部利用者による試用、Windows / Linux実機での検証も未実施です。
