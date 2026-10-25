# Architecture

CLIはplan JSONを検証し、対応するmanagedリソースを抽出します。変更のないリソースがresource_changesにない場合は、planned_valuesを再帰的に参照します。Pythonの解析はHTTPサーバー起動前に一度実行されます。入力ファイルを書き換える操作はありません。

各リソースのbefore / afterから許可リスト属性だけを抽出します。before_sensitive / after_sensitive / after_unknown、およびplanned_valuesのsensitive_valuesを再帰的に適用します。診断はサニタイズ後の値を入力とするため、機密値を根拠の文章に埋め込むこともありません。動的な診断根拠は必要最小限にしており、ルールの定型文で説明します。

Graph builderはconfiguration.root_moduleのリソース式からreferencesを読み取り、既知のリソースアドレスに解決できる場合だけedgeを生成します。参照される側から参照する側へ矢印を向けます。グラフでは矢印を省略して線で表示し、詳細パネルには参照関係を記載します。ネットワーク通信を推測しません。

サーバーは解析済みGraph（schemaVersion=1）だけを保持・配信します。APIはGET /api/graphだけで、書き込み・シェル実行・パス指定・ファイルアップロードAPIはありません。Pythonの標準ライブラリによるHTTPサーバーは個人のローカル利用専用です。

React UIはGraphを読み取り、DagreでレイアウトしReact Flowで描画します。同じnode/edgeデータを3視点で表示します。ルール追加時はrules.pyに判定を追加し、必要な属性がある場合のみsanitizer.pyの許可リストを拡張し、既知・不明・機密のテストを追加してください。

## フォーマット資料

- [Terraform JSON output format](https://developer.hashicorp.com/terraform/internals/json-format)
- [React Flow documentation](https://reactflow.dev/learn)

互換性のあるformat_version 1.x minorは受け入れ、未知の項目は無視します。未対応のmajorとactionは拒否します。


## v0.2 review boundary

`adapters.py`が入力変換の境界、`review.py`が共通結果・評価状態・比較・抑制・ポリシー、`reports.py`が表示形式、`review_cli.py`が非対話CLI、`github.py`がAPIと履歴・コメント調停、`ci.py`がActions環境の薄い連携層です。

既存parserのgraph形式は変更しません。レビューJSONは別にschema_version=1を持ち、グラフと診断に安定した識別子を加えます。過去の診断文章・設定値は比較時に転送せず、必要な識別情報だけ読み取ります。

HTMLはビルド済みReact UIとサニタイズ済み結果をインライン化します。JSONはscript終端等をエスケープし、CSPでネットワークアクセスと任意スクリプトを禁止します。React UIは埋め込み結果がある場合にAPIへ接続しません。

GitHub解析Actionはコードを実行せず準備済みplanを解析し、投稿Actionは別権限ジョブで実行します。例のworkflowでは投稿をrepository variableで明示的に有効化するまで実行しません。利用者のTerraform生成ジョブのセキュリティは利用者側の責務です。
