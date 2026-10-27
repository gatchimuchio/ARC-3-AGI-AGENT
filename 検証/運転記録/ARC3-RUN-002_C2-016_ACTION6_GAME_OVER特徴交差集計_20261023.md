# ARC3-RUN-002 C2-016 ACTION6 GAME_OVER公開特徴の交差集計

- 実施日: 2026-10-23 JST
- 指示: `運用/ARC3-RUN-002/C2-016_ACTION6_GAME_OVER特徴交差集計.md`
- 判定: **GAME_OVERは「相対中心距離middle×同色4近傍3_4」に9/15件集中。同一bucketにlevel進行もあり、避ける規則は不採用。candidate v4を維持。**
- 対象: C2-015と同じ固定dev 5公開環境×seed 7/31/73、最大80要求、GAME_OVER後SDK RESET。

## 方法と基準照合

ACTION6選択前の公開盤面から相対中心距離と同色4近傍を算出し、両方のjoint bucketに応答outcomeだけを集計した。方針、報酬、HDS、runtime、Action選択は変更せず、出力はseed別の匿名bucket件数に限定した。

previous方針のactions・levels・wins・no-op・GAME_OVER・RESET・HOLD・illegal・duplicateは、3 seedすべてでC2-003基準と一致。合計ACTION6 703回、GAME_OVER 15件、level進行3件だった。

## joint bucket集計

各セルは `GAME_OVER / ACTION6応答数 (level進行)`。

| 相対中心距離×同色近傍 | seed 7 | seed 31 | seed 73 | 合計 |
| --- | ---: | ---: | ---: | ---: |
| central × 0 | 0/19 (0) | 0/17 (0) | 0/12 (0) | 0/48 (0) |
| central × 1_2 | 1/21 (1) | 0/24 (0) | 0/22 (1) | 1/67 (2) |
| central × 3_4 | 0/12 (0) | 0/17 (0) | 0/11 (0) | 0/40 (0) |
| middle × 0 | 0/18 (0) | 0/18 (0) | 2/27 (0) | 2/63 (0) |
| middle × 1_2 | 0/40 (0) | 1/36 (0) | 1/51 (0) | 2/127 (0) |
| middle × 3_4 | 4/76 (0) | 3/67 (1) | 2/65 (0) | 9/208 (1) |
| outer × 0 | 0/8 (0) | 0/8 (0) | 0/5 (0) | 0/21 (0) |
| outer × 1_2 | 0/21 (0) | 0/22 (0) | 0/19 (0) | 0/62 (0) |
| outer × 3_4 | 0/19 (0) | 1/25 (0) | 0/23 (0) | 1/67 (0) |

middle×3_4はACTION6の208/703回（29.6%）に対しGAME_OVER 9/15件（60%）が起き、各seedでも4/3/2件と反復した。一方、level進行3件のうちseed31の1件もこのbucketにあった。残り2件はcentral×1_2だった。

## 採否と次工程

交差したGAME_OVER偏りは記述的に再現したが、同じbucketでlevel進行も生じており、安全な除外規則は確認できない。イベント数は15件、公開dev 5環境×3 seedのみで、別環境の再現、因果、予測力は未確認。ACTION6の座標選択・報酬への追加規則は作らず、holdoutも行わない。candidate version 4とKaggle kernelは維持する。

このローカル診断単位は終了。次はquota watcherによるcandidate version 4の公式Competition Rerun結果を待ち、取得したsubmission状態・score・時刻をC2-003基準線と照合する。

## 検証と証拠

- 匿名aggregate: `出力/ARC3-RUN-002-local/C2-016-action6-game-over-feature-crosstab.json`、SHA-256 `baaf48b656abafb95754dcf15688a16e765689dedae3a28f7b5717bef3f98760`。
- 診断runner `検証/ARC3ACTION6GameOver特徴交差診断.py`: SHA-256 `759d7dad0876a2fcaf5acbd12f3a77164d1dc955843b10545cd5b67374b68a88`。
- test `検証/test_ARC3ACTION6GameOver特徴交差診断.py`: SHA-256 `00691bbe30503719776eca9aee2199bb8e349418374d3fae391312748982bb6a`。
- C2-015 outcome helper SHA-256 `8ed4682874959e670ff3729817d8682a3406d979c649c811f7d3055f1b71f1ad`。評価runner SHA-256 `e9ca33c3b50b0e3b7aea1bd218aafce12418769c382ae3cecee6d37ea4f02290`。
- candidate policy SHA-256 `325666ae54197474e33b4ff46306abc7ad12c7a489d2c2c3c59585d887e26510`。Kaggle Notebook/kernelおよびofficial submission状態は変更していない。
- targeted test `1 passed`。対象Ruff check/formatとcompileall pass。
