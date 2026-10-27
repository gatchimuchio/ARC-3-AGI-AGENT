# ARC3-RUN-003 C2-039：既観測盤面への循環応答penalty ablation

## 指示・仮説

- 指示ID：`ARC3-RUN-003-C2-039`、正本v3.0。
- C1-013で、可視変化がある非終端・level非進行Actionのうち、応答先が同一run内の既観測盤面だった遷移をdev 5環境×seeds 7/31/73で20/31/22件観測。
- 仮説：既観測盤面へ戻る可視遷移のrewardに既存no-op penaltyと同じ`-1.0`を加えると、循環遷移を減らし、no-op・level進行・GAME_OVERを悪化させず探索効率を上げられる。

## 許可範囲

- `検証/`配下に隔離したpolicy subclass、paired runner、targeted testsだけを追加。提出agent・shared policy・HDS・candidate・Notebook/kernel・保護対象を変更しない。
- fixed dev split `20261022`の5公開環境、environment seeds `7/31/73`、各80 Action、GAME_OVER後RESET有効。保存trajectory再生なし。
- candidateは、Action応答後stateが`NOT_FINISHED`、level差分0、可視セル変化あり、応答盤面が同一runの既観測盤面という全条件成立時だけAction報酬を`-1.0`追加する。Action6では同じ公開応答をAction番号別と選択色別の両統計へ反映する。既存のno-op罰・UCB・係数・legal gateは保持。
- 出力はseed別匿名aggregateのみ。盤面、座標、ID、個別run、Action列を保存しない。

## 受入・採否

1. paired previous/current各15 run。開始state・初期levels・legal Actions・公開盤面が各seed5/5一致。
2. 各seedでcompleted levels/WINを維持または増加。GAME_OVER・no-op・cycle revisitは各seedで非増。illegal・duplicate・HOLDは0。
3. 次工程へ進むには全安全条件を満たし、cycle revisitが2 seeds以上で減ること。これを満たさなければ棄却しholdoutを実行しない。
4. source/input/test/output SHA、previous/current/delta、秘匿key監査を追記記録へ保存する。PASSしてもruntime採用はせず別C3指示を要する。
