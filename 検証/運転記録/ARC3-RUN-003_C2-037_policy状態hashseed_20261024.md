# ARC3-RUN-003 C2-037 実行記録（追記専用）

## 2026-10-24 JST：指示・開始前

- C1-010が次の限定課題をpolicy乱数seed変動と選定。現行main=`8667e9b9512e328084050007d3bdedb1ae5e245f`、branch `main`、origin一致を再確認。既存dirty treeを保持し、stage/commit/resetなし。
- 正確なKaggle competition slugの履歴は前工程でread-only取得済み。`57541830 COMPLETE/public 0.25/private blank`、`57527856 COMPLETE/public 0.00/private blank`。C2-037はKaggle操作を行わない。
- C2-022の初期一回hashseed版がdevの3 environment seeds全てで1 levelずつ失ったため、その仕組みは再利用せず、観測ごとのstateful decision seedのみ隔離ablationとして評価する。

## 実行状態

C2-037指示を固定。未実装・未評価。次の操作は隔離評価器・targeted testsの追加。

## 2026-10-24 JST：paired評価・棄却

- 開発split固定seed `20261022`の5環境を、environment seeds `7/31/73`、各80 Action、GAME_OVER後RESET有効で比較。各seed 5/5組の初期state・level数・legal Actions・公開盤面が一致。Action列は再生せず、毎回公開環境を実行。
- `previous`はenvironment seedをpolicy RNGにも使用。`current`は各選択時、state・公開盤面・legal Actions・同一run Action/color統計・当該盤面の座標試行数からSHA-256先頭64bitを再計算。RNG以外のpolicy、reward、UCB、合法gate、座標集合は変更なし。

| environment seed | previous levels / WIN / GAME_OVER / no-op / RESET | current levels / WIN / GAME_OVER / no-op / RESET | delta levels / WIN / GAME_OVER / no-op / RESET |
| ---: | --- | --- | --- |
| 7 | 1 / 0 / 6 / 9 / 6 | 1 / 0 / 7 / 10 / 7 | 0 / 0 / +1 / +1 / +1 |
| 31 | 1 / 0 / 6 / 9 / 6 | 1 / 0 / 7 / 10 / 7 | 0 / 0 / +1 / +1 / +1 |
| 73 | 1 / 0 / 6 / 17 / 6 | 1 / 0 / 7 / 10 / 7 | 0 / 0 / +1 / -7 / +1 |

- 全条件でactions `400`。currentのillegal `0`、duplicate observation `0`、policy HOLD `0`。合計levelは各seed `1 -> 1`、WINは`0 -> 0`。GAME_OVERは全seedで`6 -> 7`。no-op合計はseed7/31で1件増、seed73で7件減。
- 事前実装したseedごとのgate（levels/WIN非減、GAME_OVER非増、合法・lifecycle・重複・HOLD違反なし）で、全seedがGAME_OVER非増条件に不合格。C2-037は**棄却**し、C3へ進めず、提出runtime・shared policy・HDS・candidate bundle・Notebook・Kaggleは未変更。勝利・公式score改善は主張しない。
- targeted tests `4 passed`。関連回帰 `56 passed, 3 subtests passed`。Ruff check/format、py_compile PASS。
- 再現コマンド：`.venv\Scripts\python.exe 検証\ARC3policy状態hashseed評価.py`。targeted：`.venv\Scripts\python.exe -m pytest -q 検証\test_ARC3policy状態hashseed評価.py`。
- 公開入力50 files content-set SHA256 `d40c652dfffda990a1a32c65da3d873a36bb9c4b6bd06598704596af3c2ead79`。匿名aggregate output [`C2-037 JSON`](../../出力/ARC3-RUN-003-local/C2-037-policy-state-hashseed.json) SHA256 `087fca0e39bf773445a9f81e26ed285c6526dd354b546c57b87c4a8445bd924f`。禁止key scanは空。
- evaluator SHA256 `bd9c9c47ba6a6b2ecdd990dc19ca6533cba5173cafc2ce79721fbd58ee643968`、targeted test SHA256 `3b8b2895d58f60603d0e541dcf96863c5aa8d370048d7526cd0aa9513857c50e`、既存policy SHA256 `325666ae54197474e33b4ff46306abc7ad12c7a489d2c2c3c59585d887e26510`、共通評価器 SHA256 `ba8f89bf09077622f5c67e0ba310b5c2ac68d240412178a371b7e2a3f6c22088`。
- 公式Kaggle操作なし。C2-037の局所結果をsubmission `57541830`のpublic `0.25`へ因果帰属しない。次はC1へ戻り、未解決の公開故障を根拠付きで再選定する。
