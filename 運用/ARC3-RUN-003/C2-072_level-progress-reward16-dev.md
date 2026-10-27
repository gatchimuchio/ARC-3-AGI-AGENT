# C2-072 level-progress reward 16.0 dev

## 問い

25公開gameのlocal paired traceでは、探索policyのlevel進行2件は両方Action6で生じた。Action6は472回中98回がvisible no-op、mean public-response reward 0.2074。Action1-5/7のlevel eventは0。Action6でまれに起きる進行成功の価値が、4.0のlevel-progress rewardではAction UCBへ十分反映されない可能性を、係数だけ変えて調べる。

旧RUN-002のC2-005では4.0→8.0でcompleted level/完了位置/no-opに変化がなく、8.0を棄却済み。今回もdevだけの再検証であり、これを覆すには同一dev上のscore改善が必要。探索候補は16.0に限定し、Action6座標規則・HDS・visible-change係数・探索係数・action budgetは変えない。

## 固定条件

- `入力/Kaggle/environment_files`の25公開Starter環境から、`random.Random(20261027).shuffle`後のdev index 5〜9を使用。
- seed/policy-seed 7, 31, 73の同一start paired run。条件あたり最大80 actions。`retry_game_over=False`。
- baseline `level_progress_reward=4.0`; candidate `16.0`。`visible_change_coefficient=0.0`（C1-023の現行係数）を両条件に固定し、その他も同一。環境の不正action/exception/重複観測は0を必須とする。
- `PYTHONHASHSEED=0`を固定し、output JSONへ記録。公開RHAEは`ARC3公開RHAE評価._スコアを計算する`で算出。
- 出力はaggregateのみ。game ID・game別行・盤面・軌跡を保存しない。候補条件はすべて公開情報だけを使う。

## 判定ゲート

dev 15対でmean RHAE差`>=+0.01`、score改善対数が後退対数以上、level合計差`>=0`、開始状態一致15/15、不正action・exception・duplicate observationが0の場合だけ独立holdoutを計画する。それ以外は棄却し、runtime policy/HDS/Notebookへ接続しない。

## 禁止・状態

game/level ID分岐、答え/固定軌跡、hidden data、kernel push、Competition Rerun、official submission/quotaは使用しない。実験はlocal devのみで、公式competition改善とは主張しない。

## 実測結果

- 初回出力`P1-3_level-progress-reward16-dev_20261027.json`はvisible-change 0.25で実行し、C1現行係数0.0条件に一致しないため採否に使わずsuperseded扱い。
- 現行係数0.0の固定seed dev r2: RHAE `0.0926863272→0.1941233517`、差`+0.1014370245`、改善/後退/同点`1/0/14`、level差`+1`、no-op差`+3`、actions差`+12`、Action6差`+12`、GAME_OVER差`−1`。trace変更2/15、開始状態一致15/15、違法action/例外/重複観測0。改善はseed7の1対のみで、seed31/73ではtrace差があってもscore同点。
- 事前ゲートを通過したため、C2-073で別seedの検証へ進む。これはseed holdoutであり、未見game-ID holdoutとは区別する。
