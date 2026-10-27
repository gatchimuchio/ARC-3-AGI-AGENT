# C2-070 — ACTION6局所特徴memoryの学習量dev

## 問い

C2-067/069は5 trainゲーム×40 Actionで91件のAction6結果を持ち、1改善・0後退・14同点、mean ΔRHAE`+0.004360858`。その小さな正方向が学習量で安定するかを見る。

## 固定条件

- `split_seed=20261027`でshuffle後、train windows `0..4`と`10..14`の計10ゲームを各40 Action学習に使う。
- devはtrainから分離した同じ5ゲーム`5..9`、seeds `7,31,73`、80 Action上限。baselineとcandidateの開始状態・SDK合法集合・seedをpair一致させる。
- UCB weight`0.35`、prior strength、features、報酬・コードはC2-067同一。変更はtrainゲーム数だけ。
- gateは平均ΔRHAE`>=+0.01`、improvement数がregression数以上、level/WIN合計を減らさず、全start一致、illegal/duplicate/errorが0。

## 採否

gate未達ならACTION6局所パターン学習はdev段階で棄却し、Kaggle holdout/公式提出へ進まない。通過時のみshuffle index`15..24`をholdoutにする。
