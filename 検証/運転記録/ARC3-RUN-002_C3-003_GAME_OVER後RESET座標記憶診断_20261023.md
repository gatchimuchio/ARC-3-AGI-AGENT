# ARC3-RUN-002 C3-003 GAME_OVER後RESET座標記憶診断

- 実施日: 2026-10-23 JST
- 対象指示: [`C3-003指示書`](../../運用/ARC3-RUN-002/C3-003_GAME_OVER後RESET時の座標試行記憶診断.md)
- 判定: **RESET時の座標cache clearは不採用。candidate v4の記憶動作を維持。**

## 方法とprevious照合

candidate v4既定方針をsplit seed `20261022`の公開dev 5環境×Action seeds 7/31/73、各80要求、GAME_OVER後SDK RESETで再生した。GAME_OVER後の最初のNOT_FINISHED観測に対して、盤面完全一致の有無と、同じ盤面に以前保存されたACTION6座標数／公開盤面のセル数を実行中だけ比較した。盤面・座標・色・cache個票は保存していない。

各seedの初期state・合法Action集合・完了level metadataは5/5一致。C2-003 previous/currentのactions、gameplay actions、RESET、GAME_OVER、levels、no-op、WIN、HOLD、illegal、duplicateも全seedでdelta `0`。C2-003 artifactには初期盤面がないため、初期盤面のprevious照合とは扱っていない。

| seed | Actions | gameplay / RESET | levels | no-op | GAME_OVER | WIN / HOLD / illegal / duplicate |
|---:|---:|---:|---:|---:|---:|---:|
| 7 | 400 | 394 / 6 | 1 | 9 | 6 | 0 / 0 / 0 / 0 |
| 31 | 400 | 394 / 6 | 1 | 9 | 6 | 0 / 0 / 0 / 0 |
| 73 | 400 | 394 / 6 | 1 | 17 | 6 | 0 / 0 / 0 / 0 |

## 観測結果と採否

- GAME_OVER後の再開盤面は18件。16件で同じ完全一致盤面に過去のACTION6試行座標cacheが存在し、3 seedすべてで確認した。
- cache hit盤面で既試行座標が占める割合の中央値は`0.0244%`だった。事前条件の20%を大きく下回り、座標候補を実質的に狭める証拠はない。
- seed別のcache-hit詳細は小標本のため各seedとも`<10`として抑制した。盤面やrun個票を保存せず、全体集計のみを残した。
- 事前条件1と3は成立したが、条件2が不成立。reset時cache clear ablationへ進まず、現行の座標記憶を維持する。観測された再訪は、記憶が有害であることや有益であることの因果証拠ではない。

## 検証と根拠

- 新規targeted tests: `3 passed`。対象Ruff check/format、compileall pass。
- 匿名aggregate [`C3-003 run1`](../../出力/ARC3-RUN-002-local/C3-003-reset-coordinate-cache-run1.json) SHA-256 `DF29D573257EAD147976E401347DB82DB4F0C4652105DA231BFCBCFABF5EB0FB`。
- 診断runner SHA-256 `674859F5A5E19710FD9276DEDED9798F0C3B067A1CBB341F497C8615592EF0EB`、test SHA-256 `E45221C6F27CD2E4DFAB5B0CA9BFEDCA6BAE397D70368D111367B1CC1B43F2BC`。
- 対象方針SHA-256 `325666ae54197474e33b4ff46306abc7ad12c7a489d2c2c3c59585d887e26510`。runtime policy、agent、HDS、Notebook、kernel/version 4は変更していない。
- Kaggle quota watcher session `75984`は照会時点で稼働中。公式Competition Rerun/scoreは未取得であり、本診断は公式性能改善を示さない。
