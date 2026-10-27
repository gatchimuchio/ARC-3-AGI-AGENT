# ARC3-RUN-003 C1-020：公開視覚特徴からlevel進行を予測できるか

## 対象と条件

正本v3.0のC1-020指示書に従い、保存済みC2-027 model v5の公開25環境・OFFLINE event streamのみをread-onlyで解析した。評価対象は1,906 Action応答、公開`current_frame.level`の増加47件（陽性率2.466%）。run単位の固定seed 20261024・5-fold group-held-outで、base-rate、Action-only、色番号不変なvisual-only、Action+visualの固定L2 logisticを比較した。trajectoryの再生、識別子や座標による特徴化、HDS/runtime/policy/model/Notebook変更、Kaggle提出・Rerunはない。

各Action行の直前公開boardを特徴量にし、そのAction応答後に公開levelが増えたかをlabelとした。visual特徴は異なる値の個数、値頻度の順位分布、entropy、最頻値以外の行・列分布、水平・垂直の隣接不一致率。Action側は一般カテゴリ`ACTION1`〜`ACTION7`／`RESET`／`OTHER`のみ。色番号、座標、board/game/level ID、時系列番号、absolute level、Action表示文字列、score/reward、終了・評価・hidden情報はモデル入力にしない。前処理はtrain foldのみでfitした。

## 結果

| OOFモデル | PR-AUC | Brier |
| --- | ---: | ---: |
| Base-rate | 0.023249 | 0.024055 |
| Action-only | 0.024711 | 0.024062 |
| Visual-only | 0.031681 | 0.024088 |
| Action+visual | 0.022116 | 0.024105 |

Action+visual対Action-onlyのdeltaはPR-AUC `-0.002595`、Brier `+0.000043`（悪化）。対base-rateはPR-AUC `-0.001133`、Brier `+0.000051`（悪化）。Action+visualがAction-onlyを両指標で上回ったfoldは`0/5`だった。Visual-onlyのPR-AUCは高かった一方、BrierはAction-onlyより悪く、視覚特徴が安定した予測信号を加えたとは採択条件上いえない。

**採否：視覚特徴を次のHDS／学習変更へ進める仮説は不支持。** この固定特徴・固定正則化・保存済み25環境の結果に限定し、係数調整や再試験で採択を探らない。行動選択の因果効果、score改善、学習成立、hidden転移を示す結果ではない。

## 検算と検証

- C1-019との照合：Action応答1,906件、公開level遷移47件が一致。5 foldすべてに陽性例があり、run groupのtrain/test跨ぎなし。
- Targeted tests：`5 passed`。色ラベル置換不変、遷移後board不使用、公開level差分label、Action一般カテゴリ、run単位split、同点PR-AUCを確認。
- Ruff、format check、`py_compile`はPASS。
- 匿名JSON schema監査PASS。出力は全体OOF指標・delta・fold横断の単一集約値のみで、hash、個票予測、run別・fold別環境情報、board、座標、Action列、IDを含まない。
- 初回試作JSONはhash項目を含み、次の試作JSONはfold別陽性数を含んでいたため、いずれも採否用出力にせず`一時/`へ原形を保全。採否の正本は匿名集約版のみ。

## 出所SHA256

- C1-020指示書：`dfa0e1f845118a56febbd96490e782a7dc685ebfff4ad207723e32ad58f5a595`
- 解析器：`612ff5305e3e8dd71a57ea729da251a74baca29076fc1147b76cda4a13745427`
- targeted tests：`d4eea757223bad4b40923ebb017487a65c74a49967b0ad972e3140822ee8d4c7`
- candidate Notebook v5：`5763f69d0794d7161dbe81a967edd2c10a6810c92ed1a28208bd47222fd5dfbc`
- 保存prompt log：`3b88cf83db372a2c92644be47e2f4265513393e58f5957f12ab4f9d3555c553a`
- 公開25 event content set：`ae4f9546de60c5e6f6bec9c8058aebcaf1ed19a43a1383caf4c3430152814bbc`
- C1-019照合aggregate：`8b0423efa4e250898c6e1d34950eed56b5d7e528722e3fa7fbfb096c0d9accca`
- 匿名OOF集約JSON：`dc4bf89042ab2a7f46ad393da2a840b8439ba0279f6eab683513d13a8ffec392`

## 次の再開点

2026-10-24 01:41 UTCのKaggle read-only historyでC1-018提出`57577905`は`PENDING`、public/private scoreは空欄。B1 `57541830`はpublic `0.25`、B0 `57527856`はpublic `0.00`。01:33 UTCのquota照会では当日残り0件。追加提出は行わない。正本v3.0のG1-WAITとして同一IDだけをread-only追跡する。次回は`kaggle competitions submissions arc-prize-2026-arc-agi-3 --format json --page-size 20`で状態を再取得し、SCORE_READYなら公式結果と提出版を照合してG2/R4へ、PENDINGなら時刻付きで台帳へ追記する。
