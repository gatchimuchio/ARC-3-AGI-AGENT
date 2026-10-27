# ARC3-RUN-003 C1-014 実行記録：RESET後Action UCB統計持越し

- 指示：[C1-014](../../運用/ARC3-RUN-003/C1-014_RESET後ActionUCB持越し監査.md)。正本v3.0、read-only shadow監査。
- 条件：fixed dev split seed `20261022`、5公開環境×environment seeds `7/31/73`、最大80 Action、GAME_OVER後RESET有効。各seed 5 run、400 Action。
- 監査はGAME_OVER後最初のNOT_FINISHEDで、実policyと同一の乱数状態・盤面記憶・座標cacheをdeep-copyし、Action/color UCB統計だけをclearしたshadow chooserを比較。実policyのUCB統計と選択は変更せず、記録・実行されたものはprevious動作。

| seed | post-reset decisions | 初期公開条件と一致 | 既観測盤面 | legal Action総数/既試行 | 全legal既試行 | clear-shadow選択差 | levels / no-op / GAME_OVER / RESET |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 7 | 6 | 4 | 6 | 12 / 12 | 6 | 6 | 1 / 9 / 6 / 6 |
| 31 | 6 | 4 | 6 | 12 / 12 | 6 | 5 | 1 / 9 / 6 / 6 |
| 73 | 6 | 4 | 6 | 12 / 12 | 6 | 5 | 1 / 17 / 6 / 6 |

- seedごとに3回以上の同一初期条件、全legal既試行、shadow選択差の条件を満たし、3/3 seedsがC1事前支持閾値を通過。illegal/duplicate/HOLDは全seed0。これはUCB carryoverがpost-reset選択を変える頻度の証拠であり、有害性や攻略改善の証拠ではない。
- 匿名aggregate [`C1-014 JSON`](../../出力/ARC3-RUN-003-local/C1-014-reset-action-ucb-audit.json) SHA256 `c71116f7a6e8f5499e5abefa64a72cc12ed8b89055d73270273fec2ef3e5da88`。公開入力50 files content-set SHA256 `d40c652dfffda990a1a32c65da3d873a36bb9c4b6bd06598704596af3c2ead79`。禁止key監査hitなし。
- evaluator SHA256 `6c7856ae8db506391a81eeb7716ec50e34e149c9e44c9377164105b530d656b2`、targeted test SHA256 `b8fbe78b8047f3f20593ae3ff9b8c6251b6acd69f98dc0985f1b731bd908c8d3`、共通評価器 SHA256 `ba8f89bf09077622f5c67e0ba310b5c2ac68d240412178a371b7e2a3f6c22088`、policy SHA256 `325666ae54197474e33b4ff46306abc7ad12c7a489d2c2c3c59585d887e26510`。
- targeted tests `3 passed`。Ruff check/format、py_compile PASS。再現：`.venv\Scripts\python.exe 検証\ARC3RESET後ActionUCB持越し監査.py`。
- 採否：支持条件成立のため、GAME_OVER RESET後にAction/color UCB統計だけをclearする別C2-040 paired ablationを許可する。C1-014単独で性能改善を主張せず、共有policy/runtime/HDS/candidate/Notebook/Kaggleは未変更。
