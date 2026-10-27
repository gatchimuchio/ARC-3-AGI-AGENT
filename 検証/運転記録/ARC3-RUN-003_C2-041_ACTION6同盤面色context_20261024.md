# ARC3-RUN-003 C2-041 実行記録：ACTION6同盤面・色報酬context

- 指示：[C2-041](../../運用/ARC3-RUN-003/C2-041_ACTION6同盤面色報酬contextablation.md)。正本v3.0、C1-015支持後の隔離paired evaluation。
- 条件：fixed dev split `20261022`、5公開環境×environment seeds `7/31/73`、各80 Action、GAME_OVER後RESET有効。previous/current各15 live run、各seed 5/5組で初期state・levels・legal Actions・公開盤面一致。
- currentはACTION6色選択だけ、既知の同盤面・色報酬meanをUCB exploitation項へ反映。global color exploration bonus、離散Action選択、座標試行cache、報酬式、合法gate、RESETは既定のまま。

| seed | condition | levels | WIN | GAME_OVER | no-op | RESET |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 7 | previous | 1 | 0 | 6 | 9 | 6 |
| 7 | current | 1 | 0 | 6 | 9 | 6 |
| 7 | delta | 0 | 0 | 0 | 0 | 0 |
| 31 | previous | 1 | 0 | 6 | 9 | 6 |
| 31 | current | 1 | 0 | 6 | 10 | 6 |
| 31 | delta | 0 | 0 | 0 | +1 | 0 |
| 73 | previous | 1 | 0 | 6 | 17 | 6 |
| 73 | current | 1 | 0 | 6 | 17 | 6 |
| 73 | delta | 0 | 0 | 0 | 0 | 0 |

- 各条件・各seed 400 Action。illegal/duplicate/HOLDは0。levels/WIN/GAME_OVERは維持したが、no-opがseed31で1件増加、他2 seedsは不変。levels/WIN増もなし。事前improvement gate不成立で**棄却**。holdout/C3へ進まず、shared policy/runtime/HDS/candidate/Notebook/kernel/Kaggleへ採用しない。
- 匿名aggregate [`C2-041 JSON`](../../出力/ARC3-RUN-003-local/C2-041-action6-state-color-context.json) SHA256 `02be96c6fdd9cdcdd0c3cb636152dc9351a247243ebbf7be392fade822703c99`。公開入力50 files content-set SHA256 `d40c652dfffda990a1a32c65da3d873a36bb9c4b6bd06598704596af3c2ead79`。禁止key監査hitなし。
- evaluator SHA256 `e513c68801a3bcd38e6095817130ba3358fee740be4ca3c76dbcf250483f9a35`、targeted test SHA256 `600fead0c243c88d064bc3c02b7f59a367bc8a565a7100e27e17044c56c16894`、共通評価器 SHA256 `ba8f89bf09077622f5c67e0ba310b5c2ac68d240412178a371b7e2a3f6c22088`、policy SHA256 `325666ae54197474e33b4ff46306abc7ad12c7a489d2c2c3c59585d887e26510`。
- targeted tests `4 passed`。隣接評価器・policy・一巡testsはUTF-8 modeで`36 passed, 3 subtests passed`。Ruff check/format、py_compile PASS。
- 再現：`.venv\Scripts\python.exe 検証\ARC3ACTION6同盤面色contextablation.py`。Kaggle操作なし。
