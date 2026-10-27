# ARC3-RUN-003 C2-038：公開盤面・離散Action結果の文脈化ablation

## 指示・仮説

- 指示ID：`ARC3-RUN-003-C2-038`、正本v3.0。
- C1-012で同一公開盤面・同一離散Actionを代替Actionが合法な状態で選び直した23回中、公開結果カテゴリは22/24回一致（91.67%）。既定方針のAction別global UCB reward meanが他盤面の結果を混ぜる故障を検査する。
- 仮説：同じ盤面に再訪した時だけ、過去に観測した同盤面・同離散Actionの平均公開報酬を、そのActionのglobal UCB exploitation meanの代わりに使うと、再訪状態でのAction選択を改善できる。UCB探索bonusと未試行優先順はglobal baselineのまま。

## 許可範囲

- `検証/`に隔離されたpolicy subclass、paired runner、targeted testsのみを追加する。提出runtime・shared policy・HDS・candidate v4・Notebook/kernel・保護対象は変更しない。
- fixed development split seed `20261022`、5環境、environment seeds `7/31/73`、各最大80 Action、GAME_OVER後RESET有効。previousとcandidateは同じ初期公開盤面・state・levels・legal Actionsで対比較する。
- candidateが使う表は同一runで観測した公開盤面tuple × 離散Action番号1-5/7の公開応答reward count/sumのみ。ID、filename、board hash、trajectory、答え、hidden情報は使わない。ACTION6のglobal reward/color/coordinate selectionは維持。
- known state-actionがない盤面ではpreviousのglobal policyを完全維持する。既知state-actionがある盤面だけ、global reward sumの一時コピーを同盤面mean×global action countへ置き換えてbase chooserを呼び、呼出後すぐglobal統計へ戻す。global統計自体はそのまま蓄積する。探索係数・reward formula・合法gateは変更しない。
- 出力はseed別匿名aggregateのみ。board/action/per-game/trajectory rowsを保存しない。

## 受入・採否

1. targeted testsで未知盤面がbase選択と一致し、既知state-actionの報酬だけが同盤面のchooserに反映されること。global統計が呼出前後で不変であること。Action6・RESET・合法性は既定挙動のまま。
2. paired public dev 5環境×seeds 7/31/73、各80 Actionで、開始条件全15対一致・illegal/duplicate/HOLD 0。
3. 各seedでcompleted levelsとWINがprevious未満でない。GAME_OVERは各seedで非増。no-opはどのseedも増えない。
4. 次工程へ進めるには全安全条件を満たし、かつ (a) 総completed levelsまたはWINが増加、または (b) no-opが少なくとも2 seedsで減少し他seedで増加しないこと。条件未達なら即棄却しholdoutを使わない。
5. 採否時にprevious/current/delta、source/input/test/output SHA、秘匿監査を追記記録へ保存。PASSしても提出runtimeへ採用せず、別C3指示を要する。
