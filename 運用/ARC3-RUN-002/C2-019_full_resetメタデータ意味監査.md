# C2-019 指示書：full_resetメタデータの意味監査

- 指示ID: `ARC3-RUN-002-C2-019`
- 版: 1.0／2026-10-23（JST）
- 対象: C2-018で観測したno-op応答の`full_reset`差分
- 前回基準: candidate version 4、C2-018固定dev 5環境×seed 7/31/73

## 根拠

- C2-018ではno-op 35件中、盤面・level・state・公開Action集合の変化は0件だった一方、`full_reset`差分が5件あった。
- 集計artifactは匿名のrun別件数に限定し、各イベントの順序と前後値を保存していない。そのため5件が初期RESET直後のActionに対応するかは直接同定されていない。
- pinned SDK sourceでは`perform_action`が各Actionの開始時に`_full_reset=False`へ戻し、全初期化を実行したRESET応答だけが`True`を付ける構造に見える。

## 目的

ローカル公開SDKの固定版sourceと小規模な読み取り専用probeで、`full_reset`が持続的な盤面状態か、初期化応答を示すイベントmetadataかを確認する。C2-018の5件との対応に関する証拠限界を記録する。

## 許可する範囲

- pinned `arcengine`／`arc-agi` package source、`uv.lock`、C2-018匿名artifactの読み取り。
- 固定dev集合・既存seedで、各runの初期RESET後に最初の合法Actionを最大1回だけ実行し、開始・応答の`full_reset`とno-op有無を匿名集計する。
- source/package/artifact hashと、probe条件・集計値を`検証/運転記録/`に保存する。

## 禁止と保持条件

- runtime policy、HDS、agent、Notebook、Kaggle kernel、C2-018 artifactを変更しない。
- game/level ID、filename、hash、trajectory、正解・hidden情報をpolicyや診断分岐へ流入させない。
- ローカルSDKで得たmetadata意味をKaggle remote APIの保証へ一般化しない。
- C2-018の匿名aggregateから個別5イベントを同定したと主張しない。
- `AGENTS.md`、`制御/現在状態.json`、`運用/ARC3文書正本.md`、v2.0正本・v1.0履歴を変更しない。

## 検証

1. lock済みpackage versionとSDK source hashを確認する。
2. `full_reset`の設定・リセット経路・FrameData伝達をsourceで確認する。
3. 固定dev 5環境×seed 7/31/73の各runで、初期RESET直後の最初のAction応答だけをprobeし、識別子やtrajectoryを保存せず集計する。
4. C2-018の基準件数と矛盾がないか照合し、既存test・Ruff・compileall・`git diff --check`を実行する。

## 終了条件

- `full_reset`のローカルSDK semanticsと小規模probeが一致するかを示し、C2-018個別イベントとの対応限界を明記する。
- 盤面変化・Action集合変化の有無とは別指標として扱い、policyやcandidate version 4を変更しない。
- 結果とsource/artifact hashを保存し、公式Competition Rerun待ちを継続する。
