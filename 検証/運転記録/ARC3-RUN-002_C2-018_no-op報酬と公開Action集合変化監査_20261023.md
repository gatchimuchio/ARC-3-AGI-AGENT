# ARC3-RUN-002 C2-018 no-op報酬と公開Action集合変化監査

- 実施日: 2026-10-23 JST
- 対象指示: [`C2-018指示書`](../../運用/ARC3-RUN-002/C2-018_no-op報酬と公開Action集合変化の監査.md)
- 判定: **devで仮説を支持するAction集合変化なし。状態遷移も0件。policy・candidate v4を維持。**
- 対象: 固定dev 5公開環境×seed 7/31/73、最大80要求、GAME_OVER後SDK RESET。

## 方法と基準照合

既存の公開local evaluatorを読み取り専用で使い、no-op（最新盤面の変化セル数0、level進行0）の作用前後について公開`available_actions`、state、`full_reset`、frame数を集計した。開始状態は各seed・各5環境でrandom/explorationの公開盤面と合法Action集合を比較した。

開始盤面・合法Action集合は15/15対で一致。seed別の探索結果はC2-003基準と一致した。各seedで400要求、levels 1、GAME_OVER 6、RESET 6。no-opはseed 7/31/73で9/9/17、合計35。illegal Actionと重複観測stepは全て0。

## 結果

| seed | no-op | no-op中のAction集合変化 | 同一stateでAction集合変化 | state変化 | `full_reset`差分 | frame数差分 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 7 | 9 | 0 | 0 | 0 | 2 | 7 |
| 31 | 9 | 0 | 0 | 0 | 1 | 3 |
| 73 | 17 | 0 | 0 | 0 | 2 | 7 |
| 合計 | 35 | 0 | 0 | 0 | 5 | 17 |

no-op 35件では公開Action集合の変化もstate遷移も観測されず、このdev条件は「Action集合変化を伴う有効作用へno-op罰を誤適用する」という仮説を支持しない。一方、`full_reset` flag差分5件とframe数差分17件は記録した。これらの意味・因果は今回の対象外であり、Action集合変化の結論に混ぜない。

## 採否

no-op報酬規則は変更しない。HDS、runtime policy、Notebook、Kaggle kernel、candidate version 4は未変更。dev診断単位を閉じ、公式Competition Rerunの結果確認へ戻る。

## 検証と証拠

- 匿名集計: `出力/ARC3-RUN-002-local/C2-018-noop-action-set-audit-startchecked.json`、SHA-256 `c5c1f8fb552b3aaacb00725ce0c14a0ecf3655022567bfa5af7839a666ea7876`。
- runner `検証/ARC3NoopAction集合監査.py`: SHA-256 `5f1d182b210bb9209859ca87680a3f4d80566d4eeef96124c32696f6b6bf5eb2`。
- test `検証/test_ARC3NoopAction集合監査.py`: SHA-256 `5eecb146199e88ee90b86b39c149e6be68040eefac72ac53065fdebc697b31a0`。
- targeted pytest `2 passed`。対象Ruff check/format、compileall、`git diff --check` pass。
