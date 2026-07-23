# ARC-3 AGI Agent

ARC Prize 2026 / ARC-AGI-3 向けの、**未知環境を観測し、仮説を更新し、HDSの判断を経て行動する汎用エージェント**の新規実装リポジトリです。

本リポジトリは `gatchimuchio/ARC-Layer-0-Functional-Compliance` の継続改修ではありません。旧リポジトリを証拠・探索資産として凍結し、検証可能な責任境界だけを選別移植するクリーンリスタートです。

## 現在の状態

- フェーズ: `P1_EXECUTABLE_KERNEL`
- 実装状態: 独立Layer-0 kernel実装済み。P1完了判定は全unit gateで`SUSPEND`
- ベンチマーク状態: **未確定**
- 満点・AGI完成・汎化達成の主張: **なし**

旧資産には `46/183`、`97/183`、`6/183` など異なる条件・時点の数値が混在しているため、新リポジトリでは同一条件の再評価が完了するまで基準値を固定しません。

## 最上位目的

ARC-AGI-3 の未知タスクに対して、次の閉ループを実行できる汎用エージェントを構築することです。

```text
観測
  -> 表現・状態化
  -> 複数仮説と候補の生成
  -> HDSによる採否・SUSPEND・停止・rollback判断
  -> 許可された行動の放出
  -> 結果観測
  -> 記憶更新
  -> 再判断
```

スコア、部品数、分析ファイル数、実装量は代替目的にしません。

## リポジトリ構造

```text
ARC-AGI-3-Agents/             公式エージェント基盤
  arc3_agi_agent/             新しい汎用コアの責任境界
  tests/unit/                 契約・IR・検証器の単体試験
environment_files/            公式環境資産。解析・再現用であり、実行時ルーティングには使用しない
docs/
  architecture/               現行アーキテクチャ正本
  roadmap/                    段階ゲート
  migration/                  旧資産の棚卸しと移植記録
  references/                 参照仕様と引用位置
AGI_Trinity_Blueprint_v0_1.md 上位設計資料
```

ルート直下の wheel 群は現時点では既存のベンダー資産です。依存管理へ再統合するまでは、設計正本・実行時入力・ソースコードとして扱いません。

## 基盤とP1実行kernel

`ARC-AGI-3-Agents/arc3_agi_agent/` に、次を独立モジュールとして配置します。

- `protocol.py`: Pure-LLM計算主体、HDS判断主体、受動記憶主体の非対称権限
- `ir.py`: 観測、遷移、仮説、候補、閉包、証明義務の型付きIR
- `schema.py`: 決定論的シリアライズ、digest、runtime identity-free検査
- `verification.py`: 進捗・終端・危険・期待効果の保守的検証
- `checkpoint.py`: 証拠専用の有界checkpoint保持
- `context.py`: 現在・直前観測、履歴、budget、未閉包項目のbounded context
- `memory.py`: HDS許可なしでは変更できない受動memory
- `roles.py`: 六つのARC-native Layer-0責任のcallable実装
- `kernel.py`: HDS commandから結果再観測までの決定的な一循環
- `audit.py`: full setと六つのsingle-role callable removal
- `adapters/in_memory.py`: 公式runnerへ接続しない権限検証用emission境界

これらはまだ ARC-AGI-3 の標準 action-selection path へ接続していません。
P1の閉包範囲と未実装範囲は
[`docs/architecture/P1_EXECUTABLE_KERNEL.md`](docs/architecture/P1_EXECUTABLE_KERNEL.md)
に固定しています。

## 設計上の固定境界

- ARC実行時に game/task/level ID、replay index、固定action列、answer map、literal座標表、source/hidden stateを使用しない。
- Pure-LLM計算面は候補を計算・提案できるが、採用・記憶確定・外部放出を独断で行わない。
- HDSは命令・採否・SUSPEND・停止・rollback・`MEMORY_WRITE`・`EXTERNAL_EMIT`許可の唯一の判断主体とする。
- 記憶層は受動的共有状態とし、許可済み命令以外で自己更新しない。
- 観測されていない機構は事実へ昇格せず、仮説または `SUSPEND` として保持する。

詳細は [`docs/architecture/SYSTEM_ARCHITECTURE.md`](docs/architecture/SYSTEM_ARCHITECTURE.md) を参照してください。

## 検証

```bash
cd ARC-AGI-3-Agents
python -m compileall -q arc3_agi_agent
python -m unittest discover -s tests/unit -p "test_arc3_agi_*.py" -v
python -m pytest -q --confcutdir=tests/unit \
  tests/unit/test_arc3_agi_foundation.py \
  tests/unit/test_arc3_agi_kernel.py
```

## 作業順

1. P0: 再起動基盤と権限境界を固定する — 完了
2. P1: 独立Layer-0 kernelと除去監査を閉じる — 実装済み、全unit gate待ち
3. P2: HDS–計算–記憶の複数循環、rollback、再観測を閉じる
4. P3: 公式runnerへ汎用コアを統合する
5. 同一条件benchmarkを再確立する
6. アーキテクチャ完成後にのみ最適化へ進む

[`docs/roadmap/ROADMAP.md`](docs/roadmap/ROADMAP.md) が現行ロードマップの正本です。

## 参照と来歴

- 旧ARC実装・分析資産: `gatchimuchio/ARC-Layer-0-Functional-Compliance`
- 閉包・停止境界: `gatchimuchio/closure-phase-specs`
- Layer-0責任境界と除去監査: `gatchimuchio/LLM-Layer-0-Functional-Compliance-Specification`

具体的な参照commit、採用範囲、非採用範囲は [`docs/references/SOURCE_MAP.md`](docs/references/SOURCE_MAP.md) と [`docs/migration/LEGACY_ASSET_INVENTORY.md`](docs/migration/LEGACY_ASSET_INVENTORY.md) に固定しています。
