# C2-012 指示書：ACTION6中心距離順の単独評価

- 指示ID: `ARC3-RUN-002-C2-012`
- 版: 1.0／2026-10-23（JST）
- 根拠: C2-011でdev ACTION6 703回中、level進行3件のうち2件は相対中心distance bucketだった（155応答、no-op0）。2件はseed7/73、残り1件はseed31のmiddle bucketで、再現性の確証はない。仮説のみを一要因で検証する。
- 前提: 候補v4の色選択後に行う同色未試行座標の一様抽選だけを、中心距離が最小の座標集合からの一様抽選に置き換える。

## 目的

中心に近いクリック位置がdevでACTION6の進行を再現可能に増やすか測る。これは位置順の局所ablationであり、盤面中心をゲーム目標とみなさない。

## 許可する範囲と段階

1. 評価コード内に既定OFFのablation方針を置く。runtime policy source、HDS、agent、Notebook、kernel version 4は変更しない。
2. 同一dev 5環境×seed 7/31/73でprevious/candidateを比較。色選択UCB・Action UCB・報酬・Action候補・seed・80要求・RESETは固定し、同色未試行座標の選択だけを変更する。
3. devで各seedの完了levelを下回らず、総no-opを減らし、少なくとも2 seedでno-op減、GAME_OVERをseed別に増やさず、HOLD/illegal/duplicateを0に保った場合だけ未使用holdout 20環境×同3 seedへ進む。
4. holdoutでは各seedの完了levelを下回らず、no-opをseed別に増やさず総no-opを減らし、GAME_OVER/HOLD/illegal/duplicateを増やさない場合だけ採用候補とする。

## 保持条件

- 選択に使うのは現在の公開盤面、合法Action、同色セルの座標。game/level ID、filename、盤面hash、answer、hidden state、trajectoryを使わない。
- 相対距離は矩形盤面の中心から最遠角までの距離で正規化する。最小距離同点は乱数seed内で一様抽選。座標範囲と未試行制約を維持。
- 試験の出所を探索ActionとしてHDS確定と区別し、SDK step、RESET、WIN停止、80要求境界を維持。
- dev不合格ならholdoutを実行せず、local candidate/runtime変更も採用しない。holdout不合格でもversion 4を維持。

## 成果物

同条件previous/candidate/delta、dev受入、holdout実施可否、Action6 feature×outcome集計、開始状態、baseline一致、test、source/output hash、採否を `検証/運転記録/ARC3-RUN-002_C2-012_ACTION6中心距離順評価_20261023.md` に保存する。出力はseed×condition×Action群の匿名aggregateとし、既存artifactを上書きしない。
