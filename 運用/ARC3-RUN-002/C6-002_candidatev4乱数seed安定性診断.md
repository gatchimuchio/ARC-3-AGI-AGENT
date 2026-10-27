# C6-002 candidate v4 乱数seed安定性診断

## 目的

Kaggle official scoreが1回の公開結果として`0.25`となった一方、runtimeの探索方針は`random.Random(None)`で初期化され、従前の公開holdoutはseed 7/31/73のみである。candidate v4の公開性能がrun seed選択にどの程度依存するか、同じholdoutで測定する。

この診断は改善案ではなく、再現性・seed間変動を把握する観測単位である。評価器の`--seed`は`LocalEnvironmentWrapper`、探索policy、random baselineの乱数へ使われるため、環境seedとpolicy RNGの影響を分離しない。Kaggle official scoreやprivate scoreを予測しない。

## 保持条件

- runtime policy `接続/観測駆動探索Action.py`、提出agent、HDS、candidate Notebook/kernel version 4を変更しない。
- split seed `20261022`、公開holdout 20環境、Action要求上限80、GAME_OVER後SDK RESETを固定する。
- game ID / level IDを条件分岐や答え選択に使わない。集計レポートには個別ID・盤面・座標・Action列を含めない。
- 過去seed 7/31/73のC6-001結果を保持し、追加seedのみ新規artifactへ保存する。

## 実施

1. `検証/ARC3探索Actionローカル評価.py`を`--stage holdout --split-seed 20261022 --max-actions 80 --retry-game-over`で実行し、従前seed 7/31/73と追加seed 11/17/29/43/59/83/101の探索policy集計を比べる。
2. 各seedで開始盤面と合法Action集合がrandom/exploration比較において一致すること、illegal・duplicate・HOLDの有無を監査する。
3. seedごとに20 runのcompleted levels、WIN、Actions、no-op、GAME_OVER、RESETを集計し、10 seed間の範囲・中央値を算出する。random baselineは同一seed内の評価器健全性比較として保持する。
4. previous/current/deltaはseedごとの集計で示し、分散が大きい場合はどの指標で揺れるかを示す。全て匿名集計し、原因をゲーム固有のIDへ結び付けない。

## 判定と次工程

- このtaskはruntime候補の採否を行わない。run seed間でlevelsまたはWINが変動すれば公式scoreとの直接比較に使える局所再現性が限定されると記録し、policy RNGのみを分離した検査を次の指示書で行うか検討する。
- 主要指標が安定していれば、乱数制御を性能変更として導入せず、次は公開観測に対するAction因果を使ったC2/C4診断を選ぶ。
- 出力は`出力/ARC3-RUN-002-local/C6-002-seed-<seed>.json`に未使用名で保存する。最終記録は`検証/運転記録/ARC3-RUN-002_C6-002_candidatev4乱数seed安定性診断_20261023.md`へ作成し、candidate bundleは更新しない。
