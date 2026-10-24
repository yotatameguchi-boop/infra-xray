# Changelog

このファイルは利用者に関係する変更をバージョンごとに記録します。0.xは初期開発版です。

## Unreleased

変更はありません。

## 0.1.0 — 2026-10-24

### Added

- `infra-xray view` / `infra-xray check` によるTerraform 1.x plan JSONのローカル解析。
- AWSの7種類のリソースとCreate / Update / Delete / Replace / No changeの識別。
- React FlowとDagreによる2Dグラフ、ズーム、パン、検索、ノード詳細。
- Architecture / Changes / Securityの3つの表示モード。
- SG-001（SSH許可元の全IPv4への拡大）、DB-001（RDS公開設定の有効化）、OPS-001（RDS削除・置換）の診断。
- sensitive / unknown属性の扱い、属性許可リスト、ローカルAPIのトークン認証とHost検証。
- 人工planサンプル、Python / UIのテスト、ブラウザーE2E。
- MIT License、脆弱性報告方針、貢献ガイド。
- GitHub Actionsによる自動テスト・ビルドと、タグからのバージョン付きRelease公開。

### Known limitations

- 実際のネットワーク到達性、IAM、NACL、IPv6は診断しません。
- count / for_each、module出力などの曖昧な参照は推測しません。
- 複数の独立したセキュリティグループルールを統合した公開状態は評価しません。
- Windows / macOSの実ブラウザーによるCI検証は対象外です。
