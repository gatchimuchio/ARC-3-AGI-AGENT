# ARC3-RUN-003 C1-014：RESET後に持ち越されるAction UCB統計の監査

## 選定根拠

- v3のC0/C1に従い、公式B1 `57541830`（public `0.25`）以後の公開候補故障を選ぶ。C2-039は循環遷移を減らしたがno-opが全seedで増えたため棄却済み。係数調整・再試験はしない。
- C3-003ではGAME_OVER後の同盤ACTION6座標cacheの面積比が中央値0.0244%であり、reset時cache clearの根拠がなかった。一方、現在方針はGAME_OVER→SDK RESET後もAction番号別・色別UCB統計を保持する。この統計持越しが、同じ初期公開状態で既に全合法Actionを試した再試行の次Actionを変える頻度は未監査。
- 仮説：GAME_OVER後のRESETで同一初期公開条件へ戻る際、全合法Actionに既存UCB統計があり、統計を空にしたshadowでは選択が変わるなら、前attemptのAction統計が再試行の決定に実質影響する。これは有害性・能力改善をまだ示さない。

## 許可範囲・方法

- `検証/`配下のread-only evaluator・targeted testsだけを追加する。agent、shared policy、HDS、candidate、Notebook/kernel、保護対象を変更しない。
- fixed dev split seed `20261022`、5公開環境、environment seeds `7/31/73`、各最大80 Action、GAME_OVER後RESET有効。保存trajectoryを再生しない。
- GAME_OVER後の最初の`NOT_FINISHED`選択時、実Actionを変えずに同じ乱数状態・盤面記憶・座標cacheを持つdeep-copy shadowでAction/色UCB統計だけを空にし、選択差を一時比較する。実際の選択・応答は基底policyのまま実行する。
- 保存するのはseed別匿名aggregateのみ：post-reset decisions、初期公開条件との一致、既観測盤面、合法Action中の既試行数、全合法Action既試行回数、clear-stats shadowとの選択差、行動・安全集計。盤面・Action列・個別runは保存しない。

## C2候補支持条件

- 2 seed以上で、同じ初期公開条件へ戻ったpost-reset decisionがseedあたり3回以上。
- そのうち、合法Actionすべてに前attempt由来の統計があり、かつstats-clear shadowの選択が変わる事例がseedあたり3回以上。
- 条件未達ならUCB reset案のC2を作らずC1を閉じる。条件達成でもC2では安全なpaired ablationを別指示書で行い、改善は主張しない。

## 受入証拠

- 各seed 5/5 run、Action数、levels、no-op、GAME_OVER/RESET、illegal/duplicate/HOLDを保存する。
- source/input/test/output SHA256、禁止key監査、事前閾値判定を運転台帳へ追記する。
- Kaggle操作、公式score因果主張、runtime採用は禁止。
