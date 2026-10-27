# ARC3-RUN-002 S2 candidate v4 公式評価記録

## 提出対象と同一性

- Kaggle competition: `arc-prize-2026-arc-agi-3`
- Official submission ref: `57541830`
- Kernel: `tecchannn/arc3-observation-driven-exploration-candidate` version `4`
- Submission output: `submission.parquet`
- Submission description: `ARC3-RUN-002 observation-driven exploration v4`
- 受付日時: `2026-10-23 00:03:01.330 UTC`（`2026-10-23 09:03:01 JST`）
- Kaggle Notebook SHA-256: `c07059b242eccd77dcf1c482662e852db77edd86b80e7a5e231f138773f3b10b`
- Candidate source bundle SHA-256: `974029af7f66b774c96af3cf86b2344905bf68a0c83445fd366c74dd779e54d9`
- Candidate manifest SHA-256: `4988be6bf63f92b1a787b42d73a6442e7175b6fc712eeefe995854083e3c8645`
- 35 source filesのhash/byte数とNotebook内bundleをC6-001で照合済み。candidate policy/agentと提出bundleの関係は [`C6-001横断監査`](ARC3-RUN-002_C6-001_candidatev4横断回帰整合監査_20261023.md)を参照。
- ローカルHEADは`8667e9b9512e328084050007d3bdedb1ae5e245f`（`main`）。当時working treeに未コミットの開発・監査ファイルがあったため、評価対象の同一性はHEAD単独でなく上記のKaggle version・Notebook・bundle hashで固定する。

## Kaggle公式結果

2026-10-23 00:20 UTCに`kaggle competitions submissions arc-prize-2026-arc-agi-3 --format json`を再照会し、公式履歴の次を確認した。

- status: `SubmissionStatus.COMPLETE`
- public score: `0.25`
- private score: API応答は空欄、未観測
- 受付時の`PENDING`から`COMPLETE`へ遷移済み
- 受付後quota: `numToday=1`, `numTotal=5`

提出episode照会`kaggle competitions episodes 57541830`は`No episodes found`を返した。提出履歴に個別ゲーム/レベル到達、作用数、HOLD、失敗署名、実行時間はなく、非公開評価の内訳や内部因果は取得できていない。

## Previous / current / delta

| 指標 | Previous: baseline v5 | Current: candidate v4 | Delta |
| --- | ---: | ---: | ---: |
| Kaggle official public score | 0.00 (`57527856`) | 0.25 (`57541830`) | +0.25 score points |
| Official status | COMPLETE | COMPLETE | 同一 |
| Private score | 未観測 | 未観測 | 算出不可 |

両提出は同一competitionの公式public scoreで比較可能だが、Notebook/sourceが異なる。差分は提出物全体の比較であり、特定のC2/C3変更だけの因果効果とは断定しない。public leaderboard上の改善として受け入れ、hidden/private成績や全ゲーム完了を推測しない。

## 対応するローカル観測と保持条件

- candidate v4の公開holdout横断監査は60 run、4,800 Action要求、完了level合計5、WIN 0、no-op 415、GAME_OVER/RESET 29/29。bundle内policyとworkspace既定policyはAction-response列60/60で一致した。詳細はC6-001記録を参照。
- これは公開holdoutの局所指標であり、Kaggle hidden evaluationのゲーム別内訳と混ぜない。local complete levels 5をofficial scoreへ換算しない。
- 提出bundle・NotebookはC6-001でhash整合とpolicy等価性を確認済み。C6以後にcandidate sourceは変更していない。
- 次の改良は同じ公開条件で比較し、進行の悪化を防いだうえで効率差を測る。現状のKaggle public score `0.25`を最新previousとして保存する。

## 次工程

この記録をcandidate v4公式基準線として固定し、公式履歴に無い内訳を推測で補わない。C0-002で公式scoreと公開holdout結果を原因層別に整理し、次の個別改善を選ぶ。
