# C2-048: cross-level memory retention pilot

## 問題と仮説

C2-046のscorecardはslimがoffより+6.573589平均点（3 public games）だったが、Notebookの`ARC3_WM_WIPE_ON_LEVEL`を設定しておらず、既定値1でlevel transition時にWorld model/Goal model/Action model/Plan/Cross-level notesを消していた。従ってC2-046は同一level内のmemory継続を評価したが、level間の知識保持を評価していない。実装上、wipeを0にするとlevel transitionは`revise_reason="level"`へ進み、`ARC3_WM_REVISE_NUDGES=True`で保持memoryの更新を促せる。

保持した一般ルールを後続levelに適用し、scorecardを上げる。新levelに固有の盤面・状態・仮説を持ち越さないよう、level-change nudge後のWorld model/Plan更新と、古い内容の残存を監査する。

## 比較条件

- Historical control: C2-046 slim v12、同じ3 public game IDs、seed 0
- Treatment: C2-046 slim sourceに`ARC3_WM_WIPE_ON_LEVEL=0`と`ARC3_WM_REVISE_NUDGES=True`のみ追加する一体のretain-and-revise lifecycle条件
- rolling summaryは無効（既定値）。C2-047 summary候補とは混ぜず、個別効果を評価する
- model、loader、private/GPU/Internet settings、3-game limit、seed、1 pass、160 actions/game、1200 seconds/gameは固定
- C2-047 version 14がterminalになり、結果を採否判定するまで、この候補はpushしない

## primary outcomeと監査

公式`EnvironmentScoreCalculator`による3件paired scorecard。C2-046 slim mean 19.309156を超え、paired mean deltaが正であることを候補条件にする。追加でlevelごとのcompleted/score contributions、WIN、timeout、actions、memory markerのlevel境界前後の保持・改訂、memory update rejectionを集計する。開始frame/state/levelとavailable-action maskを3/3確認し、違法action増加がないこと。

負のpaired deltaや古いlevel固有の仮説混入が見られれば採用せず、nudge/keep条件を見直す。3件のprivate結果は公式Kaggle scoreでも最終確認でもない。改善が見られた場合も公開25へ進む前段階とする。

## C2-046 score decomposition target

Using the evaluator's per-level weighting and score cap, C2-046 mean score contribution by level (off → slim) was: level 1 `1.828 → 3.882`, level 2 `5.474 → 4.316`, level 3 `5.433 → 4.762`, level 4 `0 → 6.349` points per game; levels 5-7 were zero in both. Level 1 and the extra level-4 completion drove the net gain, while levels 2-3 regressed slightly despite equal completion counts. The contributions sum to the official local means within rounding. This three-game diagnostic is not causal attribution; C2-048 will inspect whether retaining/revising memory improves later-level efficiency and progression.

## 25-environment score target and continuation

The saved v5 public-25 benchmark has a verified conditional depth curve: level 1 22/25; level 2 14/22; level 3 7/14; level 4 3/7; level 5 1/3; level 6 0/1. Mean official local scorecard is 11.523217. This local three-game pilot can only nominate or reject the lifecycle change. If the paired score gate is met, continue with a 25-game matched control/treatment comparison using identical public starts, seed, loader, action/time limits, and scorecard calculation; the 25-game result, not this pilot or the old v5 subset, determines whether the score improvement generalizes.

## Official-score objective

Kaggle history read on 2026-10-24 confirms submission 57577905 COMPLETE at publicScore 23.86; privateScore was not provided. This is the official baseline to beat: only a later scored Kaggle publicScore greater than 23.86 will establish official improvement. C2-047/048/049 runs on 3 public games (and any local public-25 validation) are candidate filters and are not numerically compared with the hidden competition aggregate. The official RHAE metric weights per-level squared human/action efficiency, caps each level at 1.15, weights levels by index, caps the environment by completed-level weight, and averages across games. Final selection must improve both progression depth and action efficiency before using an official submission.

## Official-run eligibility

Before any scored rerun, reread current submission limits and confirm quota is available. The official GPU Notebook must keep Internet disabled and complete within Kaggle's 9-hour runtime requirement. The last recorded quota observation was 0 remaining at 2026-10-24 10:48 UTC; this is historical, not a current allowance.

## C2-047 review decision (2026-10-24)

C2-047 terminally completed, then was rescored with the official local `EnvironmentScoreCalculator`: mean 5.95238095 versus C2-046 slim 19.30915594, paired delta -13.35677499; all 3 matched games regressed. Exact initial event fields and baseline action arrays match for all 3. The C2-047 summary-compaction treatment is rejected as a score improvement. C2-048 is selected for the next private/offline 3-game pilot because it changes cross-level memory retention/revision on the stronger C2-046 slim base. C2-050 remains unpushed and deferred.
