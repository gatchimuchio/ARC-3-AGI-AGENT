# ARC3-RUN-002 C2-015 ACTION6 GAME_OVER直前の公開特徴診断

- 実施日: 2026-10-23 JST
- 指示: `運用/ARC3-RUN-002/C2-015_ACTION6_GAME_OVER公開特徴診断.md`
- 判定: **公開特徴にseed間で反復する記述的偏りあり。因果・予測規則としては未確認。runtime変更・holdout評価なし。**
- 対象: 固定dev 5公開環境×seed 7/31/73、最大80要求、GAME_OVER後SDK RESET。

## 方法と基準照合

C2-011と同じ選択色頻度、同色4近傍、正規化中心距離bucketを、ACTION6選択前の公開盤面から算出した。応答outcomeはGAME_OVER、level進行、level後退、no-op、board changeの排他的順で集計。出力はseed別の匿名bucket件数だけで、環境ID・座標・盤面・軌跡は保存していない。方針、報酬、HDS、runtime、Action選択は変更していない。

previous方針のdev集計はC2-003基準に全9項目×3 seedで一致した。

| seed | actions | levels | no-op | GAME_OVER | RESET | HOLD / illegal / duplicate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 7 | 400 | 1 | 9 | 6 | 6 | 0 / 0 / 0 |
| 31 | 400 | 1 | 9 | 6 | 6 | 0 / 0 / 0 |
| 73 | 400 | 1 | 17 | 6 | 6 | 0 / 0 / 0 |

## 匿名集計

ACTION6はseed別234/234/235回、計703回。GAME_OVER応答は各seed5回、計15回だった。

| 相対中心距離 | seed 7 GO/Action6 | seed 31 GO/Action6 | seed 73 GO/Action6 | 合計 |
| --- | ---: | ---: | ---: | ---: |
| central | 1/52 | 0/58 | 0/45 | 1/155 |
| middle | 4/134 | 4/121 | 5/143 | 13/398 |
| outer | 0/48 | 1/55 | 0/47 | 1/150 |

middle bucketはAction6の56.6%（398/703）を占め、ACTION6後GAME_OVERの13/15（86.7%）がここで発生した。各seedでも4/134、4/121、5/143と同じ方向の偏りがあった。観測された割合はmiddleで3.0%、3.3%、3.5%、それ以外で1.0%、0.9%、0%だった。

| 同色4近傍 | seed 7 GO/Action6 | seed 31 GO/Action6 | seed 73 GO/Action6 | 合計 |
| --- | ---: | ---: | ---: | ---: |
| 0 | 0/45 | 0/43 | 2/44 | 2/132 |
| 1_2 | 1/82 | 1/82 | 1/92 | 3/256 |
| 3_4 | 4/107 | 4/109 | 2/99 | 10/315 |

3_4 bucketにも各seedで2〜4件のGAME_OVERがあったが、中心距離との交差集計をしておらず、両特徴の独立性は確認できない。選択色頻度bucketでは、GOはseed別にdominantで1/1/1、rareで3/2/4、middleで1/2/0だった。小さいbucketの比率を個別に解釈しない。

## 採否と次工程

中心距離middleにGAME_OVERが集中する記述的な偏りは複数seedで再現した。ただしイベントは15件だけで、同色近傍との交絡、別環境での再現、Action選択との因果は未検証。C2-012の中心寄り選択はlevel進行を3→1へ落とし、C2-013の同色近傍優先は3→0へ落とした。よって本結果で座標規則や報酬係数は追加せず、candidate version 4を維持する。

固定holdoutや新しいablationには進まない。次はquota watcherによるcandidate version 4の公式Competition Rerun結果を待ち、scoreが得られた場合はC2-003基準線と比較する。公式結果未取得の間に次のローカル調査を行う場合は、中心距離×同色近傍の交差集計で偏りが同じACTION6集合に重なるかを匿名診断し、方針変更の根拠にはしない。

## 検証と証拠

- 匿名aggregate: `出力/ARC3-RUN-002-local/C2-015-action6-game-over-features.json`、SHA-256 `0f560861f988e72b7d4c5145a6938d4e64b6508986991acf01d5f680a4554d66`。
- 診断runner `検証/ARC3GAME_OVERACTION6公開特徴診断.py`: SHA-256 `8ed4682874959e670ff3729817d8682a3406d979c649c811f7d3055f1b71f1ad`。
- feature helper `検証/ARC3ACTION6座標特徴診断.py`: SHA-256 `e6235ef38ac63694e9afbb8b7973fde57a48e8145e06fd64803f7c509db71d2f`。
- test `検証/test_ARC3GAME_OVERACTION6公開特徴診断.py`: SHA-256 `458869c42eab1a4833528eb4a2259756c988c8107efe6b0ea5ecf49424d11c1d`。
- 新規単体pytest `3 passed`、C2-012/013/014を含む関連suite `19 passed`。対象Ruff check/format、compileall、`git diff --check` pass。
- 評価runner SHA-256 `e9ca33c3b50b0e3b7aea1bd218aafce12418769c382ae3cecee6d37ea4f02290`、policy SHA-256 `325666ae54197474e33b4ff46306abc7ad12c7a489d2c2c3c59585d887e26510`。
- holdout、Kaggle Notebook、candidate kernel version 4は変更していない。Competition Rerunは提出枠待ちで、scoreは未取得。
