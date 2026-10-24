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
