# ARC3-RUN-003 C2-062：現行探索方針の行動horizon比較

## 仮説

- 現行の観測駆動探索は80 request後に切ると、進行途中で終了している可能性がある。追加80 requestで公開level進行とRHAEが増えるかを調べる。
- 既存C2-029はmodel v5のprivate notebook試験で、今回の観測駆動探索policyのhorizon効果を確定しない。
- HDS guidanceの直近15対ではHDS優先Action 0件だったため、本試験は探索policy単体の隔離評価とする。HDS runtimeへの効果は主張しない。

## 固定条件と介入

- fixed dev split seed `20261022`、公開5環境、environment/policy seeds `7/31/73`、GAME_OVER後SDK RESET有効。
- previousは最大80 request、candidateは最大160 request。探索係数0.8、色係数default、報酬、座標選択、RNG seed、policy、SDK入力を固定し、上限だけ変える。
- 初期公開state/level/legal Actions/boardの一致と、previousが実行した範囲のaction引数・公開応答のprefix一致を評価器内部で照合する。個別board/action列は保存しない。
- 公式SDK `EnvironmentScoreCalculator`に沿う公開RHAEを使用。出力はseed別と全体の匿名集計のみ。

## 採否gate

1. 各seed5対の初期条件が一致し、previous実行prefixが全対でcandidateと一致する。illegal/duplicate/scorecard contract errorは0。
2. candidateの平均RHAE差が正、completed level総数が非減、paired score regressionsが0である場合のみ、固定holdout 20環境×同seedへ進む。
3. 条件未達ならC2-062を棄却し、holdoutもruntime・HDS・提出Notebookへ反映しない。
4. dev/holdout通過も探索horizonのローカル効果に限る。shared runtime採用・公式score主張には別の検収が必要。

## 禁止・出力

- game/level ID、盤面、filename、hashによるpolicy分岐、固定trajectory再生、hidden/evaluator情報の利用は禁止。
- HDS、shared policy、提出agent、candidate bundle、Notebook/kernel、Kaggle API、公式提出・quotaは変更・使用しない。
- source/input/output SHA-256、初期/prefix一致件数、previous/current/delta、採否を運転台帳へ記録する。
