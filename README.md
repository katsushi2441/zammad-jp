# Zammad 日本語翻訳補完 (zammad-jp)

[Zammad](https://github.com/zammad/zammad)(オープンソースのヘルプデスク/チケット管理)の
日本語UI翻訳を補完した `zammad.ja.po` を配布します。

本家に同梱されている日本語翻訳はカバレッジが低く(実測: 有効5,123エントリ中、翻訳済みは約23%)、
管理画面やメール通知テンプレートの多くが英語のまま表示されます。このリポジトリのpoファイルは
未訳ぶんをすべて埋め、**有効エントリの翻訳カバレッジ100%**にしたものです。

## 適用手順（セルフホスト向け）

```bash
# 1. poファイルを差し替える（パッケージ版の例。パスは環境に合わせる）
sudo cp zammad.ja.po /opt/zammad/i18n/zammad.ja.po

# 2. 翻訳をDBへ同期する
zammad run rails r 'Translation.sync'
#   ソースインストールなら: rails r 'Translation.sync'

# 3. ブラウザを再読み込み（プロフィール言語が日本語であることを確認）
```

Zammadは起動時/パッケージ更新時にもpoを読み込みます([公式の解説](https://community.zammad.org/t/custom-translation/3019))。
個別の文言はZammad管理画面の翻訳カスタマイズでも上書きできます。

## 翻訳方針

- 機械翻訳(ローカルLLM中心)ベース+一部手訳。**追加した全エントリでプレースホルダ(%s, %{name},
  #{ticket.title}等)・HTMLタグ・URL・改行の逐語一致を機械検証**し、不一致の訳は採用していません
- 本家由来の既存訳(約23%ぶん)には手を加えていません
- 用語統一: Ticket=チケット / Agent=担当者 / Customer=顧客 / Organization=組織 /
  Overview=一覧 / Trigger=トリガー / Escalation=エスカレーション など
- 誤訳の指摘・改善PRを歓迎します

## 本家への貢献

Zammadの翻訳は[Weblate](https://translations.zammad.org/)で集中管理されています。
本リポジトリの訳文は、Weblateへ提案する際の下訳としても利用できます。

## ライセンス

翻訳はZammad本体と同じ[AGPL-3.0](https://github.com/zammad/zammad/blob/develop/LICENSE)で提供します。
