# C4-004 指示書：事前記憶のruntime適用境界監査

- 指示ID: `ARC3-RUN-002-C4-004`
- 版: 1.0 / 2026-10-23（JST）
- 区分: 読み取り専用の記憶・HDS接続監査

## 根拠と目的

現行AGENTS.mdおよびARC3 v2.0はHDS v0.4.2・事前記憶v0.4を保持対象とし、事前記憶の利用と学習状態更新を開発優先項目に挙げる。同時に、ゲームID/レベルIDによる答え参照、固定Action列、成功trajectory再生を禁止する。現在の提出agentは新規HDSを生成するため、事前記憶の内容・形式がそのままruntime適用できるかを安全境界とHDS永続化契約から判定する。

## 調査対象

- `記憶/事前記憶/v0.4/README.md`、`マニフェスト.json`、`183レベル_HDS索引.json`、`機構作用既知解_HDS正本.json`
- `HDS/学習系統/v0.4.2/hds学習系統/永続化.py`およびHDS読込契約
- `接続/ARC3提出agent.py`のHDS初期化、候補照会、action応答処理
- 既存C1-002 HDS shadow学習評価。重複する解析を再実行しない。

## 保持条件と手順

1. 各入力ファイルのSHA-256、件数、top-level categoryを確認し、game/level IDやtrajectoryの値を作業ログ・新規成果物へ複製しない。
2. 事前記憶の内容を次の区分に集計する: ID/levelに結び付く索引・作用統計、再現済み既知解trajectory、ID-freeの横断蒸留ルール。
3. 現行HDSのloaderが受ける永続化schemaと事前記憶JSON schemaを照合する。必要ならJSONを読むだけのin-memory互換性検査を行い、例外内容に個別ID等を出さない。
4. 提出agentがどのHDS状態を生成・照会・更新するか、C1-002報告と現行コードで追跡する。

- 事前記憶、HDS core、提出agent、AGENTS.md、現在状態、v2.0正本は編集しない。
- IDつき索引、既知解、trajectoryをruntimeへ接続しない。既存memoryを答え表として実行しない。
- ID-free文章の一般性を、実装可能・検証済みの規則と読み替えない。
- Kaggle Notebook/kernelや公式提出は変更しない。

## 完了条件

- 事前記憶の安全な利用可能範囲、loaderとの互換性、runtimeの実際のHDS状態更新範囲を分けて記録する。
- 正本の変更なしで、SHA・件数・証拠・採否を運転記録へ保存する。
- 汎用部分を機械実行できる条件が成立しなければ無理に接続せず、次の改良候補を選ぶ。
