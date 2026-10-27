# ARC3-RUN-003 C1-011 実行記録：同一公開盤面の既知no-op再選択監査

- 指示：[C1-011](../../運用/ARC3-RUN-003/C1-011_state-action再訪機会の公開監査.md)。v3.0／ARC3-RUN-003。read-only policy subclassのみ。
- 条件：固定dev split seed `20261022`、5公開環境、environment seeds `7/31/73`、各seed400 Action・394 policy decisions、最大80 Action/run、GAME_OVER後RESET有効。

| seed | board revisit | known no-op legal | known no-op + alternative | selected known no-op + alternative |
| ---: | ---: | ---: | ---: | ---: |
| 7 | 34 | 8 | 4 | 0 |
| 31 | 45 | 12 | 5 | 0 |
| 73 | 44 | 14 | 10 | 1 |

- 合法Actionは各run内でSDK直前検査。illegal、duplicate、policy HOLDは全seed0。座標Action6は対象外。
- 事前gate「既知no-op再選択10回以上かつ2 seeds以上」を満たさず、C2候補はunsupported。盤面別no-op回避を再実装せずC1-011を閉じる。
- 公開入力50 files content-set SHA256 `d40c652dfffda990a1a32c65da3d873a36bb9c4b6bd06598704596af3c2ead79`。匿名aggregate [`C1-011 JSON`](../../出力/ARC3-RUN-003-local/C1-011-state-action-revisit-audit.json) SHA256 `b19c84ec1e6c191d9f8e6dfa2a3567b9fab5d10ace31afb3b69bb959a807afcb`。禁止key監査は空。
- evaluator SHA256 `c44c042a3c17d5486439990517dff130c2dbca85a5d123424d19df57f63e801b`、targeted test SHA256 `0cc0e649bf86004f2c0edc3ee211af11a2c9981b7d0f8925aacb08d7bb6c8eb2`、共通評価器 SHA256 `ba8f89bf09077622f5c67e0ba310b5c2ac68d240412178a371b7e2a3f6c22088`、policy SHA256 `325666ae54197474e33b4ff46306abc7ad12c7a489d2c2c3c59585d887e26510`。
- 再現：`.venv\Scripts\python.exe 検証\ARC3stateAction再訪監査.py`。tests `3 passed`、Ruff/format/py_compile PASS。
- 次工程C1-012は、既知no-opに限らない同一公開盤面・Action結果カテゴリの再現性監査。C1-011からruntimeへの変更・性能主張なし。
