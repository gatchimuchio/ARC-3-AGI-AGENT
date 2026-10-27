# ARC3-RUN-002 C1-005 中間Frame差分no-op罰開発ablation

- 実施日: 2026-10-23 JST
- 指示: `運用/ARC3-RUN-002/C1-005_中間Frame差分no-op罰の開発ablation.md`
- 判定: **開発受入条件FAIL。ablation不採用、holdout未実施、candidate v4維持。**
- 対象: 固定dev 5公開環境、seed 7/31/73、各80要求、GAME_OVER後SDK RESET。

## 比較条件

previousは候補v4の既定報酬（no-op `-1.0`）。candidateは評価コード内だけの実験方針で、非RESET・最新盤面不変・clamped level増分0・中間gridのいずれかが最終gridと異なる場合だけno-op罰を+1.0相殺する。他係数、Action UCB・ACTION6色UCB、選択ロジック、seed、予算は同じ。製品方針`接続/観測駆動探索Action.py`やKaggle bundleへflagを追加せず、通常評価は既定OFF。

実行前後盤面・合法Action集合は15/15対比較で一致。previousのseed別出力は保存済みC2-003 dev artifactのactions/levels/no-op/GAME_OVER/RESET/WIN/HOLD/illegal/duplicate集計すべてに一致した。

## 結果

| Seed | no-op previous | no-op candidate | 差分 | 完了level previous→candidate | GAME_OVER previous→candidate |
|---:|---:|---:|---:|---:|---:|
| 7 | 9 | 11 | +2 | 1→1 | 6→6 |
| 31 | 9 | 11 | +2 | 1→1 | 6→6 |
| 73 | 17 | 12 | -5 | 1→1 | 6→6 |

3 seed合計no-opは35→34（-1、-2.9%）だが、減少したのはseed73だけ。seed7/31では各2件増えた。ACTION6 no-opは各seedで4→7、4→7、6→8と全て増加。ACTION1/3/4等の減少で総数がわずかに下がったものの、各seedの完了level、総Action要求400、GAME_OVER、RESETは変わらず、WINは0。policy hold・違法Action・重複stepも両条件0。

事前条件「総no-op減少かつ2 seed以上で減少」を満たさない。ACTION6のno-op増加も全seedに共通し、候補となる進行改善は見られないためholdoutへ進めない。C1-004の中間grid/no-op相関は、それ自体では罰免除を正当化しなかった。

## 検証と証拠

- 全体Ruff check PASS、接続/検証 compileall PASS。関連targeted suite `25 passed`（現行探索方針、C1-003/004監査、C1-005実験）。`git diff --check`はwhitespace errorなし。既存CRLF/LF警告のみ。
- 匿名aggregate: `出力/ARC3-RUN-002-local/C1-005-intermediate-noop-ablation.json`、14,552 bytes、SHA-256 `b9dde7e7d71b7f658702d3045c3d88f1cb263d73dc5dcc27da91b1e1b40d50a2`。
- ablation runner `検証/ARC3複数FrameNoop罰ablation.py` SHA-256 `26a947323f5cb9ad56eadc0c4048a1790f4e4266d0714bc6affe5b82b800ade3`。
- 評価runner `検証/ARC3探索Actionローカル評価.py` SHA-256 `8a45dbc0c1e6ac9829a83ebfcbf11f905b972c8711eefe411e9c859faadbd7a0`。候補方針`接続/観測駆動探索Action.py` SHA-256 `325666ae54197474e33b4ff46306abc7ad12c7a489d2c2c3c59585d887e26510`で変更なし。
- test `検証/test_ARC3複数FrameNoop罰ablation.py` SHA-256 `655cb0b476be1c1d2598e935488e3d3b33cd8182b1120caa723cbc4e8feffa53`。
- 再実行: `python -m uv run --locked python -X utf8 検証/ARC3複数FrameNoop罰ablation.py`。既存artifactを上書きしないため、再実行時は未使用の`--output`を指定する。
