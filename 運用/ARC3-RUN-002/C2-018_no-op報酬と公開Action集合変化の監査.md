# C2-018 指示書：no-op報酬と公開Action集合変化の監査

- 指示ID: `ARC3-RUN-002-C2-018`
- 版: 1.0／2026-10-23（JST）
- 対象: 観測駆動探索Actionのno-op判定と公開`available_actions`
- 前回基準: C2-017終了時点のcandidate version 4。公式Competition Rerunはquota待ち。

## 根拠

- 現行候補は、公開盤面の変化セル数が0かつlevel進行が0の応答へUCB報酬`-1.0`を加える。
- 観測境界は盤面・状態・level数・`available_actions`を保持するが、報酬判定は盤面とlevel数だけを参照する。
- 公開Action集合だけが変わる応答が存在するなら、それは観測可能な状態変化を伴う。該当応答も現在はno-op罰となる。
- そのような応答がdevで発生するか、どの後続状態へつながるかは未計測。

## 目的

固定candidate v4方針のまま公開dev環境で、盤面不変・level進行なしの応答における`available_actions`、状態、reset flag、frame数の変化を読み取り専用で集計する。no-op罰の誤分類仮説に観測根拠があるか判断する。

## 許可する範囲

- `検証/`に評価専用の計測runnerとその集計testを追加。
- 既存の公開local evaluatorを使い、固定dev 5環境×seed 7/31/73、最大80要求、GAME_OVER後RESET有効で実行。
- 作用前後の公開観測から特徴を数える。保存artifactは匿名集計とseed別値に限定。
- C2-003のprevious/current再現値、開始盤面・合法集合を照合。

## 禁止と保持条件

- `接続/観測駆動探索Action.py`、`接続/ARC3提出agent.py`、HDS、Notebook、Kaggle kernelを変更しない。
- game ID、level ID、filename、hash、保存trajectory、正解・hidden情報を特徴分岐やpolicyへ流入させない。
- 監査中に`available_actions`変化を有益・有害な報酬と決めつけない。
- `AGENTS.md`、`制御/現在状態.json`、`運用/ARC3文書正本.md`、v2.0正本とv1.0履歴を変更しない。

## 検証

1. testで、盤面不変・level不変・Action集合変化を他の変化と区別して数える。
2. dev 5環境×3 seedをC2-003と同じ条件で実行し、previous/currentの開始盤面・合法集合・levels/no-op/GAME_OVER/RESETが基準と一致することを確認する。
3. no-op応答のうちAction集合だけが変化した数、状態だけが変化した数、reset flag/frame数の変化数を匿名集計する。
4. targeted tests、Ruff、compileall、`git diff --check`を実行し、runner・test・出力hashを記録。

## 終了条件

- 公開観測差分の分母・分子・seed別内訳と基準一致を保存する。
- 該当が0件なら誤分類仮説をdev内で支持せず、policyを変更せず終了する。
- 該当があっても因果・有用性を確定せず、policyを変更せず終了する。必要な介入比較は新しい指示書に分ける。
- candidate version 4を維持し、公式Competition Rerun待ちを継続する。
