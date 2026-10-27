# ARC3-RUN-003 C2-040 実行記録：RESET後Action UCB統計clear

- 指示：[C2-040](../../運用/ARC3-RUN-003/C2-040_RESET後ActionUCB統計clearablation.md)。正本v3.0、C1-014支持後の隔離paired evaluation。
- 条件：fixed dev split seed `20261022`、5公開環境×seeds `7/31/73`、各80 Action、GAME_OVER後RESET有効。previous/current各15 live run、各seed 5/5組で初期state・levels・legal Actions・盤面一致。
- currentはGAME_OVER後RESETの次のNOT_FINISHED観測で最初のゲームActionを選ぶ直前に限り、Action番号別の回数/報酬合計/総作用数とACTION6色別の回数/報酬合計をclear。盤面記憶・座標試行cache・RNG・報酬・合法gateは維持。

| seed | 条件 | levels | WIN | GAME_OVER | no-op | RESET | reset stat clears |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 7 | previous | 1 | 0 | 6 | 9 | 6 | 0 |
| 7 | current | 1 | 0 | 7 | 15 | 6 | 6 |
| 7 | delta | 0 | 0 | +1 | +6 | 0 | +6 |
| 31 | previous | 1 | 0 | 6 | 9 | 6 | 0 |
| 31 | current | 1 | 0 | 5 | 18 | 5 | 5 |
| 31 | delta | 0 | 0 | -1 | +9 | -1 | +5 |
| 73 | previous | 1 | 0 | 6 | 17 | 6 | 0 |
| 73 | current | 1 | 0 | 6 | 21 | 6 | 6 |
| 73 | delta | 0 | 0 | 0 | +4 | 0 | +6 |

- 各条件・各seedのactionsは400。currentのclear countは実RESET回数と一致（6/5/6）。illegal/duplicate/HOLDは両条件0。levels/WINは不変だが、no-opは全seedで増加し、seed7ではGAME_OVERも1件増加。事前の安全・改善gateに不合格のため**棄却**。holdout/C3へ進まず、shared policy/runtime/HDS/candidate/Notebook/kernel/Kaggleへ採用しない。
- 初回実行artifact [`C2-040初回JSON`](../../出力/ARC3-RUN-003-local/C2-040-reset-action-ucb-clear.json)はclear回数のrunner集計漏れがあり、検証に使用しない。集計を修正し同じ固定条件で再実行したvalidated artifact [`C2-040 JSON`](../../出力/ARC3-RUN-003-local/C2-040-reset-action-ucb-clear-verified.json) SHA256 `8a76248eb3507776c6d97998ebb6da7d93388ff351f788e8a4b0d119fef591de`。公開入力50 files content-set SHA256 `d40c652dfffda990a1a32c65da3d873a36bb9c4b6bd06598704596af3c2ead79`。禁止key監査hitなし。
- evaluator SHA256 `fe1ebc537d75b84141451ba96a151cc7be291830044550af1b6d5b02423c83b9`、targeted test SHA256 `9d2fe674180bad37283d1458758ac6a425341b82937eda695fd22ec81d0be4d6`、共通評価器 SHA256 `ba8f89bf09077622f5c67e0ba310b5c2ac68d240412178a371b7e2a3f6c22088`、policy SHA256 `325666ae54197474e33b4ff46306abc7ad12c7a489d2c2c3c59585d887e26510`。
- targeted tests `4 passed`。隣接評価器・policy・一巡testsは`.venv\Scripts\python.exe -X utf8 -m pytest -q ...`で`36 passed, 3 subtests passed`。Ruff check/format、py_compile PASS。
- 再現：`.venv\Scripts\python.exe 検証\ARC3RESET後ActionUCBclearablation.py`。Kaggle操作・公式提出なし。
