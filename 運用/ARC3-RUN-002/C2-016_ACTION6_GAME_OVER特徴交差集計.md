# C2-016 指示書：ACTION6 GAME_OVER公開特徴の交差集計

- 指示ID: `ARC3-RUN-002-C2-016`
- 版: 1.0／2026-10-23（JST）
- 根拠: C2-015でGAME_OVERは中心距離middleに13/15、同色4近傍3_4に10/15あった。両特徴が同じACTION6応答へ重なるかは未確認。
- 目的: 二つの周辺bucket偏りが同じACTION6集合によるものかを匿名集計し、別個の特徴と誤認しないようにする。

## 方法

- C2-015と同じ固定dev 5公開環境×seed 7/31/73、現行candidate-v4相当方針、最大80要求で再実行する。
- ACTION6の選択前公開盤面から相対中心距離×同色4近傍のjoint bucketと、排他的応答outcome件数だけを集計する。
- C2-003 baselineとの一致をseedごとに確認する。不一致なら集計は無効。
- policy、報酬、HDS、runtime、Action選択は変更しない。識別子、座標、盤面、軌跡は保存しない。

## 判定境界

- joint bucketは同じ標本からの探索的記述に限る。因果・予測・安全規則、holdout適格性、公式scoreへの効果を主張しない。
- 交差結果だけで規則・係数を採用しない。candidate v4およびKaggle kernelは維持する。

## 成果物

- seed×relative-center-distance×same-color-neighbors×outcomeの匿名集計、baseline一致、tests、source/output SHA-256、解釈境界を `検証/運転記録/ARC3-RUN-002_C2-016_ACTION6_GAME_OVER特徴交差集計_20261023.md` に記録する。
