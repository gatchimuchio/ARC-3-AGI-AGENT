# C1-009 指示書：事前盤面形状特徴のshadow予測評価

- 指示ID: ARC3-RUN-002-C1-009
- 版: 1.2／2026-10-23（JST）
- 根拠: C1-006〜008で直前Frame要約はAction別多数派を超えず、Frame shadow枝を閉じた。C2-010ではAction応答後の進行は集計したが、Action選択直前の盤面特徴は評価していない。

## 目的・仮説

現在Action番号だけのHDSに、Action直前の公開盤面から作る小さな色分布要約を加え、同一dev環境内の時系列heldoutで予測価値を測る。Action応答後のFrame/結果は条件へ含めない。仮説は、現在盤面の色多様性と最多色の占有率がAction応答結果をAction別多数派以上に識別すること。

## 方法

- 固定dev split seed 20261022の先頭5公開環境、environment seed 31、policy seed 7/31/73、各最大80要求。
- 作用前最新gridから、色種類数を1–2 / 3–4 / 5以上へ、最多色の占有率を50%以下 / 50%超〜75% / 75%超へ離散化し、単一の「事前盤面色分布帯」値へ合成する。Action番号と合成カテゴリの2条件を使う。HDSの現行最大関係条件数が2であるため、合成カテゴリとして扱う。色番号、grid寸法、位置、盤面値は条件へ渡さない。
- 各環境・seedごとに新規HDSを作り、適格Action応答列先頭75%を学習、後半25%をread-only照会する。
- previousはAction-only HDS、currentはAction番号＋事前盤面色分布HDS、基準は同じ訓練行のAction別多数派。結果は可視変化、level進行、新規盤面。
- 条件は作用前に観測された盤面だけから構成する。RESET応答・比較不能gridは除外する。出力はseed別aggregateだけで、環境別行・盤面・色値・予測条件値は保存しない。

## 事前採否

各結果targetについて、盤面条件HDS・Action-only HDS・Action別多数派の三者共通coverageが全policy seed合計で30件以上あり、盤面条件HDSが共通集合で両baselineを上回り、3 policy seed中2 seed以上で正のdelta、残るseedでも負でない場合だけ、別指示でcross-environment転移を検討する。成立しなければ特徴をruntimeへ接続せず、holdoutにも進まない。

## 保持条件・成果物

ID分岐、固定Action列、hidden/evaluator情報、問題固有の色値判断を使わない。AGENTS.md、現在状態、HDS、提出agent/runtime、candidate/Notebook/kernelは変更しない。評価器、tests、匿名aggregate、source/input hash、previous/current/delta、採否をC1-009運転記録へ保存する。Kaggle実行はしない。
