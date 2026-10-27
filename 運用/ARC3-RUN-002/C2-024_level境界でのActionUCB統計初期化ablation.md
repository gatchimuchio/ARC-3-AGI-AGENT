# C2-024 指示書：level境界でのAction UCB統計初期化ablation

- 指示ID: `ARC3-RUN-002-C2-024`
- 版: 1.0 / 2026-10-23（JST）
- 対象: 評価専用のAction番号別UCB統計

## 根拠と目的

C6-003の公開holdout 10 policy seedでは、level進行報酬のAction別記録に欠落はなかった。一方、現行policyはAction番号別の回数・報酬統計をlevelをまたいで保持し、盤面色別統計も保持する。levelごとに有効な操作特性が異なる場合、前levelのAction平均報酬が次levelのUCB選択へ残る可能性がある。

C4-001はAction・色など全方針統計のreset、C4-002/003は色統計だけのresetを既に評価しており、いずれもcandidate runtimeへ採用していない。本taskはAction番号別UCBの回数・報酬・総回数だけをresetし、色統計を残す成分分離であり、既存の両ablationの再実施ではない。

Action番号別の`_回数`・`_報酬合計`・`_総作用数`だけを次level開始時に初期化し、level境界を越えるAction統計の持越しが公開devの効率へ影響するか調べる。Action 6色統計、乱数状態、観測盤面記憶、座標試行記憶、報酬係数は維持する。

## 方法

- baseline: 現行candidate v4相当の既定policy。
- candidate: 初回次level観測を検知した後、次Action選択の直前にAction番号別UCB統計だけを空にする評価専用ablation。
- `完了レベル数`の増加を公開境界信号として使い、game/level ID、盤面hash、色ID、軌跡、hidden stateは使わない。
- split seed `20261022`、dev公開5環境×seed `7/31/73`、最大80要求、GAME_OVER後SDK RESETで対比較する。
- 初期公開状態・合法Action、Actions、完了levels、no-op、GAME_OVER/RESET、WIN/HOLD/illegal/duplicateをseed別・合計で記録する。個別game・盤面・trajectoryはレポートへ出さない。

## 変更範囲と保持条件

- evaluatorのablationとtargeted testだけを追加する。提出runtime、`接続/観測駆動探索Action.py`、HDS、Notebook/kernel、candidate v4は変更しない。
- Action統計を初期化するのは完了level数が増えた次levelでの最初の選択前とする。直前levelの進行報酬の記録処理は妨げない。
- Action 6色別の`_色回数`・`_色報酬合計`は維持し、C4-002/003の色統計resetと混同しない。
- 乱数seed/state、既観測盤面、座標試行、no-op回避状態、可視報酬は変更しない。
- seed選別・問題固有条件・成功軌跡再生をしない。

## 事前採否条件

devを通過し未使用holdoutへ進む条件は全て満たすこと。

1. 各seedで開始公開状態と合法Actionがbaseline/current全環境と一致する。
2. completed levelsが3 seed全てbaseline以上。
3. no-op総数が減少し、seed別で2/3以上悪化しない。
4. GAME_OVER総数は増加しない。WIN/HOLD/illegal/duplicateはbaselineより増えない。

一つでも不合格ならablationを棄却し、未使用holdoutへ進まずcandidate v4を維持する。条件を通ってもlocal結果だけで競技性能改善を主張しない。

## 成果物と完了

- 指示どおりの評価専用ablation、targeted tests、匿名summaryを作成。
- previous/current/delta、seed別gate、source/test/summary SHA-256、採否を`検証/運転記録/ARC3-RUN-002_C2-024_level境界ActionUCB統計ablation_20261023.md`へ記録。
- 不採用なら次の優先課題を選び、candidate v4と公式submission記録を保持する。
