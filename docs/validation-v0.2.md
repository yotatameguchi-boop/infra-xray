# v0.2 検証記録

開発日: 2026-10-25。ローカル環境: macOS arm64 / Python 3.9.6 / Node.js 24。

## ローカルで通過

- Python: 101件。既存55件を含む。
- Vitest: 7件。既存6件を含む。
- TypeScript型チェック、Viteビルド。
- 解析・レポート・ポリシー・抑制・期限・前回比較・不明状態・機密カナリア。
- 入力上書き拒否、出力サイズ上限、原子的な出力、生成済み結果の保持。
- GitHub APIの再試行、投稿無効化、権限不足、Botコメント識別、古いSHAとrun、fork拒否、署名付きURLへのトークン非転送。
- 過去のポリシー違反runからの基準取得、PR・target・SHA・runの検証。

## GitHub Actionsで通過した項目

初回実行: [テスト・ビルド](https://github.com/yotatameguchi-boop/infra-xray/actions/runs/40157444319) / [複数plan解析](https://github.com/yotatameguchi-boop/infra-xray/actions/runs/40157444327)。初回CIはPython 100件、Vitest 7件、Playwright 3件で通過。追加した異常レポート境界のテストを含む最終結果はPRチェックを参照。

- Linux / Python 3.12 / Node.js 22の全テストとwheel / sdist / ZIPビルド。
- 既存のブラウザーE2E 2件と、オフラインHTMLの実ブラウザーテスト1件。
- 自己完結HTMLをfile URLで開き、ネットワーク無効でもグラフ・詳細・検索が動くこと。
- 悪意あるscript終端・img・イベント属性を含む入力が実行されず、機密カナリアがHTMLに含まれないこと。
- 2つの人工planを同一PRで解析するActionsの実例。

PRコメントのAPI処理はモックで検証します。このリポジトリでは投稿を初期設定で無効に保ちます。外部利用者のリポジトリや実AWS環境での確認、Windows / macOSの実ブラウザーCIは対象外です。

100リソースのreview生成＋JSON出力を30回測定し、中央値1.885 msでした。環境と計測範囲は `review-performance.json` に記録しています。性能保証ではありません。
