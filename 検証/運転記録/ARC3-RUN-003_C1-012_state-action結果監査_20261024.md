# ARC3-RUN-003 C1-012 実行記録：同一公開盤面・離散Action結果再現性

- 指示：[C1-012](../../運用/ARC3-RUN-003/C1-012_state-action結果再現性監査.md)。v3.0／ARC3-RUN-003。既定探索policyを変更しないlive-run observer。
- 条件：固定dev split seed `20261022`、5公開環境、environment seeds `7/31/73`、各seed400 Action・394 policy decisions、最大80 Action/run、GAME_OVER後RESET有効。ACTION6座標Actionは除外。

| seed | board revisit | same board/action再選択（合法alternativeあり） | outcome category一致 / 不一致 |
| ---: | ---: | ---: | ---: |
| 7 | 34 | 6 | 6 / 0 |
| 31 | 45 | 8 | 9 / 0 |
| 73 | 44 | 9 | 7 / 2 |

- 代替合法Actionありの同一盤面・同一離散Action再選択は合計23回で、全seedに分布。公開結果カテゴリ比較は24回中22一致・2不一致（91.67%）。post-reset decisionsは各seed6、初期盤面再訪各seed4、reset直後の同一state-action再選択は0/0/1。
- illegal、duplicate、policy HOLDは全seed0。Action選択、RNG、報酬、UCB、HDS、runtimeは未変更。
- 事前gate（再選択10回以上・2 seeds以上・結果カテゴリ一致率80%以上）を満たし、state-action reward contextualizationの限定C2候補を支持。ただしこの監査単独では能力改善・採用を主張しない。
- 公開入力50 files content-set SHA256 `d40c652dfffda990a1a32c65da3d873a36bb9c4b6bd06598704596af3c2ead79`。匿名aggregate [`C1-012 JSON`](../../出力/ARC3-RUN-003-local/C1-012-state-action-outcome-audit.json) SHA256 `b7a51ca08537c12439dcfe4987d2fef1d0d10b832fae80dbf21dbdbfac690c40`。禁止key監査は空。
- evaluator SHA256 `02a26677899314d9948c48518cdd7316ef9ec3e9c939cadb687498df4df543dc`、targeted test SHA256 `09e53f392a2bd8eb8926d87467cabf2fdd49297d2ff7c34e3383889629158494`、共通評価器 SHA256 `ba8f89bf09077622f5c67e0ba310b5c2ac68d240412178a371b7e2a3f6c22088`、policy SHA256 `325666ae54197474e33b4ff46306abc7ad12c7a489d2c2c3c59585d887e26510`。
- 再現：`.venv\Scripts\python.exe 検証\ARC3stateAction結果再現性監査.py`。tests `3 passed`、Ruff/format/py_compile PASS。
- 次工程C2-038は同一盤面上の既知Action response rewardだけをglobal UCB exploitation meanへ反映する評価専用ablation。result不一致・hidden state alias・性能回帰なら棄却する。
