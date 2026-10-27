# C5-001 指示書：Action要求上限の公開環境診断

- 指示ID: `ARC3-RUN-002-C5-001`
- 版: 1.0／2026-10-23（JST）
- 対象: 候補version 4相当の観測駆動探索Action要求上限
- 基準: per-game 80 Action、C2-003採用方針

## 根拠と仮説

C2-003の20 holdout環境×seed 7/31/73の60 runは、全て`action_limit`でちょうど80 Action終了し、WINは0だった。公式starterの`Agent.MAX_ACTIONS=80`はagent側の無限ループ防止上限であり、`MyAgent.MAX_ACTIONS=79`が実際に80回の要求を許す。上限だけを160、必要なら320へ増やすことで、追加の合法探索が公開level完了を増やす可能性がある。一方、GAME_OVER/no-op/実行時間/記録量が増えて競技実行を損なう可能性がある。

## 範囲と保持条件

- C2-003の探索方針、報酬係数、RESET・座標選択、HDS、Action選択を変更しない。
- AGENTS.md、制御/現在状態.json、v2.0正本ポインタ、HDS v0.4.2、過去Notebook版を変更しない。
- 最初はdev 5環境だけで80/160/320をseed 7/31/73比較し、上限はdevだけから選ぶ。holdoutで調整しない。
- fixed holdout 20環境×seed 7/31/73は、devが条件を満たした選択上限を一度だけ評価する。
- game/level ID、filename、hash、固定軌跡、答え表でActionを選ばない。
- 評価結果は公式score・hidden性能として扱わない。

## 手順と判定

1. 保存済みC2-003の80-action JSONとSHAを基準として固定する。
2. `検証/ARC3探索Actionローカル評価.py`でdevを80、160、320 Actionまで実行し、各seedの開始状態が同じことを確認する。
3. 最大上限は、80よりdev合計level完了が増え、WIN/illegal/duplicate/探索HOLDが悪化せず、実行時間・artifactサイズが許容範囲の最大値から選ぶ。160が改善しなければ320を評価する。いずれも改善しなければ80を維持し、holdoutは実施しない。
4. 選択上限をholdout20環境×seed 7/31/73へ一度だけ適用し、80-action基準と比較する。devで選んだ上限は変更しない。
5. 採用候補なら公式starterの`MyAgent.main()`経路を実環境1件以上で確認し、要求数・経過時間・ピークメモリ/記録量が運転制約に収まることを測る。Kaggleのwall-clock枠・日次提出枠は別途確認する。
6. 採用する場合のみ`MAX_ACTIONS`を最小変更し、統合test、全体回帰、bundle閉包検証を通す。Kaggle候補Notebookはその後に新versionとして作り、通常実行を確認する。

## 成果物

dev/holdoutのprevious/current/delta、完了level・Action数・GAME_OVER/RESET・WIN・no-op・HOLD・illegal/duplicate、経過時間・JSONサイズ・SHA、採否、次の課題を `検証/運転記録/ARC3-RUN-002_C5-001_Action上限診断_20261023.md` に記録する。artifactは`出力/ARC3-RUN-002-local/`に保存し、既存出力を上書きしない。
