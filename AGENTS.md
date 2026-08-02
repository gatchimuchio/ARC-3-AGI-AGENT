# ARC3 Codex開発契約 rev4

このrepositoryの現在目的は、HDSでARC3成功軌道をタスク分解し、ARC3エージェントが使用する汎用構造と命令形Pを抽出・実装することである。

## 正本

1. Ownerの現在の明示指示
2. `docs/strategy/ARC3_HDS直接抽出_汎用構造命令形P_実装仕様書_rev4.md`
3. `docs/roadmap/ARC3_HDS直接抽出_開発ロードマップ_rev4.md`
4. `control/rev4/CURRENT_TASK.json`
5. HDS／AGI上位正本

rev3のD/B/A/E phase、`control/rev3/REV3_CURRENT_SELECTOR.json`、旧P0〜P22、S0〜S6は履歴であり、current task selectorではない。

## 最上位目的

```text
25 game／183 levelの成功軌道
→ HDS TaskDecompositionRecord
→ GenericStructureLibrary
→ Imperative PBundle
→ 同一ARC3 Agent
→ 183/183実行
→ 公式提出
```

## 現在作業

```text
P1_TASK_DECOMPOSITION
```

- 全25 game／183 levelを列挙する。
- 各成功軌道をbefore／target／condition／operation／effect／progress／terminalへ分解する。
- terminalから逆向きに寄与stepを結ぶ。
- 全stepを機械可読TaskDecompositionRecordへ変換する。
- 不明項目は`open_terms`へ置き、推測で閉じない。

## HDSの使い方

HDSは成果物ではなく判断方法である。

```text
F  観測を切り取る
Md 構造候補と反対候補を作る
Cm 採否・保留・観測要求を決める
U  結果を分解記録、構造、P、M、Failure Signatureへ反映する
```

## 許可

- 既知回答・成功軌道・raw recording・canonical trajectoryの使用
- 最大情報で抽出してからidentity／replay依存を減算すること
- 既存IR／interpreter／P16〜P21 substrateの再利用
- repository内の実装・試験・修正の連続実行
- failureから前工程へ戻ること

## 禁止

- 新repositoryの作成
- HDS理論証明を主目的にすること
- schema／digest／attestation／approval専用phaseの追加
- source-blind証明を抽出開始条件にすること
- game ID／level IDだけによるruntime action routing
- fixed trajectory replayを汎用Pとして扱うこと
- 次工程が読まないartifactの作成
- 仕様外のBridge／Runtime／公式作業の先行

## 工程

```text
P1 Task Decomposition
P2 Generic Structure Extraction
P3 Imperative P Compilation
P4 Agent Integration
P5 Full Execution Repair Loop
P6 Official Packaging / Evaluation
```

これ以外のTrackを追加しない。

## 成果物規則

新artifactは次のいずれかを満たす場合だけ作る。

```text
次工程のコードが直接読む
失敗修正に直接使う
公式提出に必要
```

各phaseのprimary artifactは一系統、verification reportは一つまでを原則とする。

## 検証

- testは各work unitの末尾で行う。
- test専用phaseを作らない。
- test数を成果と数えない。
- 実際のcoverage、実行結果、failure解消を成果とする。

## Owner権限

Ownerは最上位目的、戦略変更、PBundle freeze、公式提出を決める。内部の連続開発は、明示的な停止指示または重大な仕様衝突がない限り継続する。
