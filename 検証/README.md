# 検証

検証は「実装した」と「成立した」を分離する。

証拠の強さ:

```text
E0 文書・構造・artifact存在
E1 syntax / static / unit
E2 local integrated / offline
E3 ARC3公式sample
E4 Kaggle normal run
E5 official accepted score
```

上位claimを下位Evidenceで代用しない。既知trajectoryや事前記憶を利用した成功と、未観測状態・未観測levelへの転用を別々に記録する。

失敗、未確認、反例は隠さずHDSの次判断へ渡す。
