# C2-090 / C2-091 HDS Action 6 座標特徴診断

## 目的と適用指示

作業開始時にARC26 v6.0の共通3文書とARC3専用3文書をすべて再確認した。対象はARC3のみ。ブランチ`codex/arc3-v6-progress-20261027`、開始HEAD `13edb89c741ba0d6bc9303cf4e4f31a688307a12`。

C2-089ではHDSに座標Action 6の一般照会を加えても、公開dev 15組すべてで予測候補0、RHAE差0だった。本診断では原因を分けるため、固定した公開開始点1・seed 7・80 action上限で、(1) Action 6規則の有無、(2) Action 6の実選択回数、(3)既存の粗い状態特徴と座標由来の公開特徴が応答区分をどの程度分けるかを観測した。座標特徴は診断内だけで算出し、提出agent/HDS/探索方針へは追加していない。

## 条件

- Python 3.12.10、`arc-agi==0.9.8`、`arcengine==0.9.3`、HDS v0.4.2。
- 公開25環境metadata manifest、split seed `20261022`、その先頭公開開始点、SDK seed 7、最大80 action。
- 使用コマンド：`& '.venv\Scripts\python.exe' '検証/ARC3HDSAction6RuleDiagnostic.py'`および`& '.venv\Scripts\python.exe' '検証/ARC3HDSAction6FeatureFeasibility.py'`。
- HDS記憶マニフェストSHA-256：`d1b6e0cc3d14ce7c40c26567feFA226a2975c2e6d02725fb8bb404833963a1bd`。
- ローカルpublic RHAEは単一診断エピソード値であり、比較スコアではない。

## 観測結果

### C2-090: queryと学習成立の診断

- 80回すべてでAction 6の一般照会を試行。各時点で「Action番号＋作用前公開状態」に一致する有効原理は0件で、予測・競合・追加観測要求も0件。照会状態は全80回`断定保留`。
- 実際に選ばれた操作はAction 6が76回、Action 7が2回、RESETが2回。RESETを除くHDS更新は78回で、Action 6選択回数と応答記録件数は一致した。
- エピソードは80 actionで`GAME_OVER`、0 level、0 WIN、1 no-op、local RHAE 0.0。これは診断対象の基準線で、Action 6照会variantとの性能比較ではない。

### C2-091: Action 6応答を分ける公開特徴

- Action 6の76応答は「盤面変化」73件、「可視変化なし」3件。レベル進行・勝利は0件。
- 現行HDSへ渡す粗い状態特徴は、この走行ではそれぞれ単一値しか取らず、その値に両応答が混在した。作用可能数`2`、色種類数`6`、最多色占有帯`高`はいずれも1カテゴリ内で競合するため、Action番号と組み合わせても決定的な規則を作れない。
- 選択座標から診断用に計算した対象セル色は6カテゴリで、全カテゴリ内の応答が一貫した。色3/5/9は盤面変化が各23/27/23件、色0/4/15は可視変化なしが各1件だった。
- 同色連結成分帯・4近傍数・外周・位置帯はこの走行で競合を残した。したがって、この1開始点では「対象セル色」が候補特徴として最も明確だが、単発かつ同一ゲーム内の観測であり、他ゲームへの転移もスコア改善も未確認。

## 判断

C2-089のgeneric Action 6照会は不採用のまま。原因を「Action 6の一般応答は一定」とは見なせず、**選択座標に結び付く文脈を学習入力から落としていることが、当該公開走行の規則不成立と整合する**と判明した。次は対象セルの公開特徴をHDS照会へ加える検証専用variantを作り、既存と同じ5開始点×seed 7/31/73の同条件RHAEで評価する。色値のゲーム間意味は未確認のため、1走行の決定性だけでruntime/mainへ採用しない。

提出agent、HDS、探索方針、Notebookは変更していない。Kaggle公式提出・Competition Rerun・quota使用なし。公式得点の更新を意図した実験ではない。

## 証拠

- C2-090 query-only初回結果：`運用/証拠/ARC26-UNIFIED/ARC3-C2-090-HDS-Action6-query-diagnostic-20261027.json` SHA-256 `d3594bc752e1e5d24322d6daccfa3241ceae02adf6a2d284018158b192c93e84`。
- C2-090 action count付き再実行：`運用/証拠/ARC26-UNIFIED/ARC3-C2-090-HDS-Action6-query-diagnostic-with-action-counts-20261027.json` SHA-256 `ddd9ca0ca0311710a525bd87dd6bee2c07972a5cb7b55cb051993131b7ffba9a`。
- C2-090 runner：`検証/ARC3HDSAction6RuleDiagnostic.py` SHA-256 `924e7c262ea95ee3a5e32fc65b75e35e864b792f8a159dbafa9712775c745f96`。
- C2-091 feature feasibility：`運用/証拠/ARC26-UNIFIED/ARC3-C2-091-HDS-Action6-feature-feasibility-20261027.json` SHA-256 `5a46cb73daef57221c327e8359d23b25331c3bab50ecd710aaa27ff9dadaee8e`。
- C2-091 runner：`検証/ARC3HDSAction6FeatureFeasibility.py` SHA-256 `23955d546bc33c73c18b8a507427e49da323c97c90a38a83b2f55113ad503d49`。
- 両runnerの`py_compile`とRuff確認は通過。作業時点のHEAD・保護ファイルに変更なし。
- push前の全行JSON検証で、HEAD以前からwork-ledger 222行目とscore-ledger 55行目に隣接JSON recordが改行なしで連結されていたことを確認した。2箇所とも元recordのbyte列は保持し、境界へLFを1つ挿入してJSONLとして修復。既存recordの値は変更していない。修復内容と最終report hashはcanonical work-ledgerへ追記する。
