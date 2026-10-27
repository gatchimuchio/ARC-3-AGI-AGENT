# C2-049: rolling-summary turn-context pilot

## 仮説

C2-047の要約生成はturn opener作成前に実行される。既定の`ARC3_SUMMARY_TURN_CONTEXT=False`では、直前のlevel transitionは履歴内の`level_completed` flagとしてしか見えず、要約が完了済みlevelを現在levelとして記す恐れがある。埋め込み実装のコメントもこの誤りを明示している。summary requestに直前の実行内容・level変更・現在step/levelを渡せば、要約が履歴置換後も現在状態を保ち、level間の進行を助ける可能性がある。

## 比較条件

- Baseline: C2-047 version 14の同一3公開offline game。C2-047が有効なsummaryを作成し、履歴置換まで到達したことを先に確認する。
- Treatment: C2-047 notebookへ`ARC3_SUMMARY_TURN_CONTEXT=True`のみ追加。interval 32,768、履歴置換、モデル、memory、loader、seed、action/time budgetは固定。
- 現候補はローカル準備のみ。C2-047 version 14がterminalになり、そのログを確認するまでpushしない。
- private/GPU有効/Internet無効。公式competition rerun・submission・quota使用なし。

## 観測・採否

同じ3初期状態で公式ローカル`EnvironmentScoreCalculator`を用いて採点し、C2-047に対するpaired score delta、levelごとの進行/WIN、transition直後のsummary状態、summary failure/truncation、request/prompt/completion token、timeoutを記録する。summary callと履歴置換が確認できない場合は実験を実行せず、その機能経路を先に調べる。3-run pilotは候補選別に限り、昇格には同条件の公開25-run比較を要求する。改善未確認の変更をmainへ採用しない。

## 採用ゲート

- まずC2-047との差でturn-context設定の効果を分離する。
- 3-game pilotを次段階へ進める条件は、C2-047に対してpaired mean deltaが正で、かつ同じ3公開gameでの現行best C2-046 slim mean 19.309156も上回ること。scoreだけでなくlevel depth、timeout、WINを確認する。
- 有効なsummary生成と履歴置換が観測されなければC2-049は実行しない。
- pilot通過後も、現行bestとの同条件matched public-25比較を通るまで採用・公式改善を主張しない。

## Official-score objective

Kaggle history read on 2026-10-24 confirms submission 57577905 COMPLETE at publicScore 23.86; privateScore was not provided. This is the official baseline to beat: only a later scored Kaggle publicScore greater than 23.86 will establish official improvement. C2-047/048/049 runs on 3 public games (and any local public-25 validation) are candidate filters and are not numerically compared with the hidden competition aggregate. The official RHAE metric weights per-level squared human/action efficiency, caps each level at 1.15, weights levels by index, caps the environment by completed-level weight, and averages across games. Final selection must improve both progression depth and action efficiency before using an official submission.

## Official-run eligibility

Before any scored rerun, reread current submission limits and confirm quota is available. The official GPU Notebook must keep Internet disabled and complete within Kaggle's 9-hour runtime requirement. The last recorded quota observation was 0 remaining at 2026-10-24 10:48 UTC; this is historical, not a current allowance.
