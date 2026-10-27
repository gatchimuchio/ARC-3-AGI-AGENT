# ARC3-RUN-002 C2-023 Action 5/6 報酬統計反映監査

- 実施日: 2026-10-23 JST
- 対象指示: [`C2-023指示書`](../../運用/ARC3-RUN-002/C2-023_Action5_Action6報酬統計反映監査.md)
- 判定: **level進行報酬がAction別UCB記録へ反映される経路に欠落は見つからない。Action 6の色別反映はコード上確認したが、artifactに個別色統計がないため実行値までは照合していない。runtime/candidate v4は維持。**

## コード経路

現行`接続/観測駆動探索Action.py`は公開level差分を`増分=max(0, 完了レベル数の差)`として算出する。既定応答報酬は`4.0 × 増分 + 0.5 × 新盤面 + 0.25 × 正規化可視変化 - 1.0 × (可視変化なし・進行なし)`。同じ報酬がAction番号別の回数・報酬合計へ加算され、次のAction選択では平均報酬とUCB探索項`0.8 × sqrt(log(総作用数)/Action回数)`を使う。Action 6の場合は選択時の公開盤面色にも同じ報酬が色別統計として加算され、色UCB値の計算に使われる。

## C6-003記録との照合

固定environment seed `31`、公開holdout20環境、policy seed 10条件、合計200 run・16,000探索応答を集計した。Action 5/6の`level_delta`、応答内に記録された完了level増分、game単位の`policy_action_stats`を照合したところ、level増分とAction別回数・報酬合計は全て一致した。

| Action | 選択回数 | 完了level増分 | 進行率 | no-op | GAME_OVER | 公開報酬合計 / 平均 |
|---:|---:|---:|---:|---:|---:|---:|
| 5 | 1,691 | 3 | 0.1774% | 74 | 25 | 682.871277 / 0.403827 |
| 6 | 3,949 | 24 | 0.6077% | 910 | 32 | 667.346619 / 0.168991 |

Action 5の進行3件は10 policy seed中3 seedに分布し、Action 6の進行24件は10 seed全てに分布した。進行報酬成分はAction 5で合計12、Action 6で合計96。Action 6の平均報酬が低いのは進行報酬が無視されたためではなく、他の報酬項目を含む集計である。選択頻度・進行率・平均報酬の関係はこの公開holdout記録内の観測であり、因果やhidden環境への転移を示さない。GAME_OVER件数自体は現在の報酬式に独立した罰項として入っていない。

色別統計はpolicy応答artifactに保存されないため、Action 6の色統計についてはコード経路だけを確認した。実行時の色別回数・報酬が一致するとの主張はしない。

## 採否と次工程

Action 5/6のlevel進行増分は応答報酬とAction別最終統計へ正しく届いていたため、修正は不要。公開holdoutを使った追加tuningも行わない。Action・色統計のlevel間保持は別の文脈問題であり、次単位C2-024ではAction番号別UCB統計だけをlevel境界で初期化する開発split ablationを、色統計を維持したまま試す。C4-002/003の色統計resetとは対象が異なる。

## 根拠

- 入力匿名summary: [`C6-003 summary`](../../出力/ARC3-RUN-002-local/C6-003-policy-seed-summary.json)、SHA-256 `7B5B8AF263B9D0FB0509F259D16CB6D16268DB4E085E0F7C492503885241834F`。
- 現行方針SHA-256 `325666AE54197474E33B4FF46306ABC7AD12C7A489D2C2C3C59585D887E26510`。
- 10 seed別JSONは公開game情報・応答列を含む既存evaluation artifactであり、本レポートにはgame ID・盤面・座標・個別trajectoryを転載していない。
- 読み取り専用監査のためsource変更・新規test・candidate/Notebook/kernel更新なし。
