# ARC3-RUN-003 C2-036 実行記録（追記専用）

## 2026-10-24 JST：指示・開始前基準

- 正本はv3.0／`ARC3-RUN-003`。`運用/ARC3文書正本.md`で確認。AGENTS・保護状態・v3三文書を再読し、保護対象は変更しない。
- 基底Git SHA `8667e9b9512e328084050007d3bdedb1ae5e245f`、branch `main`、`origin/main`一致。既存dirty treeを保持し、stage/commit/resetなし。
- Kaggle正規slug `arc-prize-2026-arc-agi-3`のread-only historyを2026-10-24 JSTに再取得。`57541830 COMPLETE / public 0.25 / private blank`、`57527856 COMPLETE / public 0.00 / private blank`。公式提出・Rerunなし。
- 評価器は公開環境のmetadata・OFFLINEデータ50 filesを読み、split seed `20261022`でdev 5環境を選択する。公開C2-003結果は実行条件の確認だけに参照し、保存Action列は読込・再生しない。公開content-set SHA-256 `d40c652dfffda990a1a32c65da3d873a36bb9c4b6bd06598704596af3c2ead79`。
- 既存C1-002はAction結果要約によるHDS学習とheldout結果予測を評価したが、学習後に`公開観測から候補を照会する()`がAction候補を変えるかは未評価。A0は空HDSの公開25初期状態でAction候補0件。候補更新経路の有無を調べるためC2-036を作成した。
- 調査時刻にPowerShell PATHから`kaggle`コマンドが見つからなかったため、repo `.venv`の`python -m kaggle`を使い同じhistoryを取得。CLIは2.2.4で2.2.5更新通知を表示したが、今回updateなし。公式score履歴以外のKaggle操作なし。

## 実行状態

C2-036開始。live public exploration trajectory上のHDS shadow比較器・testsを作成する。候補Actionは選択・実行に使用せず、公式提出/評価なし。

## 2026-10-24 JST：live shadow評価・採否

- 固定条件でlive policyが各現在観測からActionを選択。公開環境5件×最大80 requestで計400 Action、non-RESET Action 394、SDK RESET 6。levels合計1、WIN 0、illegal Action 0、no-op 9。saved trajectoryの再生なし。
- 394件のnon-RESET応答すべてをAction番号・可視変化有無・level進行有無・新規盤面有無へ要約し、環境ごと独立したlearned HDSへ`処理する()`を呼出した。状態版変化12回。empty-controlへの学習呼出0。
- 同一の394公開観測でempty-controlとlearned HDSを各1回照会。両側合計788回の`観測台帳`件数が照会前後で不変。すべての候補は非実行許可かつ現観測のlegal Actionであることを評価器が検査した。
- previous empty-control候補数0、current learned-HDS候補数0、delta 0。394 paired observationすべてでcandidate set差0。結果は5環境・policy seed31の局所試験であり、公開攻略や公式得点の効果を意味しない。
- 匿名artifact `出力/ARC3-RUN-003-local/C2-036-HDS-action-candidate-shadow.json` SHA-256 `e5687461b8b787c0f7e965caa4be93ffc1c52511a917c5c66fb08bd51ca12316`。出力に個別環境・Action列・board/coordinate/GUIDはなく、禁則keyを含まないことを検索確認。
- evaluator SHA-256 `1c40cb69a96baa71622ad1f6c2bf6e481f904174c28226b616dbc1c88d4bda51`、targeted test SHA-256 `56316b874bcd6f633887c541199bcf03a2533be212fe4031580a096f9e11319a`、指示SHA-256 `b86826011a9c593dea27617534314103aa9603e6543be273d015fa9798803750`。
- targeted/regression suite (`C2-036`, `C1-002`, common candidate router, exploration policy, candidate agent): `46 passed, 3 subtests passed`。Ruff check/format、py_compileはPASS。`git diff --check`に既存3ファイルのCRLF→LF警告のみ、errorなし。
- 採否：**経験更新後もAction候補生成へ変化しないため、Action-result HDS bridge案を棄却。** HDS core、runtime、candidate v4、Notebook/kernel、事前記憶、保護対象は無変更。C3やholdoutへ進めずC1に戻る。
- 次：C0/C1の原因・優先度をC2-036反証込みで再評価し、ID-freeで根拠のある別の上流故障が存在する場合のみ次の一指示書を作成。candidate v4の公開score `0.25`は内部game-level原因を開示しないため、この失敗に公式scoreの原因帰属を行わない。
