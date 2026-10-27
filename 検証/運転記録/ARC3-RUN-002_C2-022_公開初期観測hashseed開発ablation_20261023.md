# ARC3-RUN-002 C2-022 公開初期観測hash seed開発ablation

- 実施日: 2026-10-23 JST
- 対象指示: [`C2-022指示書`](../../運用/ARC3-RUN-002/C2-022_公開初期観測hashseedの開発ablation.md)
- 判定: **hash seed導入は不採用。devの全seedで完了levelを1失い、未使用holdoutへ進めない。runtime、candidate v4、Notebook/kernelは維持。**

## 条件と実装範囲

公開dev 5環境、environment seed 7/31/73、各環境最大80 Action、GAME_OVER後RESET、split seed `20261022`で、現行policyと公開初期観測hash seedを比較した。hash seed materialは最初の`NOT_FINISHED`観測にある状態・盤面・昇順の合法Action集合だけで、game/level ID、filename、trajectory、hidden情報を使わない。評価専用flagとテストのみを`検証/ARC3探索Actionローカル評価.py`、`検証/test_ARC3探索Actionローカル評価.py`へ追加した。

## previous / current / delta

| environment seed | 条件 | Actions | 完了levels | no-op | GAME_OVER / RESET | WIN / HOLD / illegal / duplicate |
|---:|---|---:|---:|---:|---:|---:|
| 7 | baseline → hash seed | 400 → 400 | 1 → 0 (**-1**) | 9 → 9 (0) | 6/6 → 5/5 (-1/-1) | 0 / 0 / 0 / 0 維持 |
| 31 | baseline → hash seed | 400 → 400 | 1 → 0 (**-1**) | 9 → 9 (0) | 6/6 → 5/5 (-1/-1) | 0 / 0 / 0 / 0 維持 |
| 73 | baseline → hash seed | 400 → 400 | 1 → 0 (**-1**) | 17 → 9 (-8) | 6/6 → 5/5 (-1/-1) | 0 / 0 / 0 / 0 維持 |
| 合計 | baseline → hash seed | 1,200 → 1,200 | 3 → 0 (**-3**) | 35 → 27 (-8) | 18/18 → 15/15 (-3/-3) | 0 / 0 / 0 / 0 維持 |

全5環境の開始公開状態・合法Action・予算は対になった。seed 31のhash seed条件を同じ条件で再実行し、探索Action記録が5/5完全一致した。再現性、no-op合計、GAME_OVERの条件は満たしたが、事前条件の「全seedでcompleted levelsを維持」を3/3 seedで失ったため失格とした。hash-seed効果のholdout評価は行わない。

## 採否・保持対象

hash seedは評価専用の開発実験として棄却する。レベル進行の低下をno-op/GAME_OVER減少で相殺して採用しない。提出runtime、HDS、Notebook/kernel、公式candidate v4、保護対象には変更なし。公式submission `57541830`のpublic score `0.25`は既存の結果として保持し、このablationとの因果関係は主張しない。private scoreは未観測。

## 検証・証拠

- targeted tests: `5 passed`。Ruff check、Ruff format check、compileall、`git diff --check` pass。
- 匿名集計: [`C2-022 summary`](../../出力/ARC3-RUN-002-local/C2-022-hashseed-dev-summary.json)、SHA-256 `0BB462E7E7E980E0805219C8ECF8D5D095C9578DEA7BCBD5618BFA38B8DF303D`。summaryにgame ID・trajectoryはない。
- 評価器SHA-256 `1E3D889EE67FBB4284A4DF2DA504DBB6A7F7BBD47B450AD72F8AA1FCB31C8E3A`、targeted test SHA-256 `310290F330C5573BFD09DA41AC5A9C7738EEA161DFB47152A3AA5601DF6CA659`。
- 個別baseline/hashseed artifact SHAはsummary内に記録。レポートへ個別IDや盤面情報は転記していない。

次単位はC2-023として、C6-003の固定環境・10 policy seed公開結果と現行UCB実装を読み取り専用で照合し、Action 5/6のlevel進行信号がAction別・ACTION6色別報酬統計へ実際に反映されるか監査する。
