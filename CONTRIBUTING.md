# Contributing

不具合報告、診断ルール、表示改善、ドキュメントへの貢献を歓迎します。大きな変更は、着手前にIssueで目的と対象範囲を相談してください。脆弱性は[SECURITY.md](SECURITY.md)の非公開窓口を使用してください。

## 開発環境

Python 3.9以上、Node.js 22、npm、Gitを用意してください。

```bash
git clone https://github.com/yotatameguchi-boop/infra-xray.git
cd infra-xray
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e . pytest build
cd web
npm ci
npm run build
cd ..
infra-xray view examples/synthetic-plans/review.json
```

Windowsでは仮想環境の有効化に `.venv\Scripts\activate` を使います。UIを変更したら `web` 内で `npm run build` を再実行し、ブラウザーを更新してください。CLIが起動時にplanを解析するため、planやPythonコードの変更後はCLIを再起動します。

## 変更の確認

```bash
python -m pytest -q
cd web
npm test
npm run build
npx playwright install chromium
npx playwright test
cd ..
python -m build
```

PlaywrightはローカルCLIを起動し、スクリーンショット・動画・100ノードの表示時間を生成します。制限付き環境でブラウザーが起動できない場合はその事実をPRに記載し、GitHub Actionsでの確認結果を確認してください。

## 実装上の原則

- 解析・サニタイズ・グラフ・診断・UIの責務を分けます。
- 新しい診断ルールには、検出ケース、非検出ケース、unknown / sensitiveのテストを追加してください。
- 属性の追加は `sanitizer.py` の許可リストをレビューし、機密値がAPIやログに出ないことを検証してください。
- 推測した通信経路や依存関係を確定情報として表示しません。
- テストやスクリーンショットには人工データだけを使ってください。
- UIのビルド成果物は `infra_xray/static` にあります。UI変更と一緒に更新してください。

## Pull Request

1. forkから作業ブランチを作成します。
2. 変更内容、理由、確認したテスト、既知の制限をPR本文に記載します。
3. 必要に応じてCHANGELOGのUnreleasedを更新します。
4. Actionsのテスト・ビルドが成功したことを確認します。

貢献はこのプロジェクトの[MIT License](LICENSE)の下で提供してください。

## メンテナー向けリリース

`pyproject.toml`、`setup.py`、`infra_xray/__init__.py`、`web/package.json`のバージョンを揃え、lockfileとCHANGELOGを更新します。通常のブランチでCIを通してから `vX.Y.Z` タグをpushしてください。

タグのActionsは全テスト・ビルドに成功した場合だけ、wheel、sdist、実行用ZIP、SHA256SUMSをGitHub Releasesに公開します。`0.x`はプレリリース扱いです。タグとPythonパッケージのバージョンが不一致の場合は失敗します。配布物生成は `python scripts/package_release.py` で再現できます。
