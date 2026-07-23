# ARC-3 AGI Agent

ARC Prize 2026 / ARC-AGI-3向けの、**未知環境を観測し、命令形保持体をLayer-0で計算し、HDSの判断を経て行動する汎用エージェント**の新規実装リポジトリです。

本リポジトリは `gatchimuchio/ARC-Layer-0-Functional-Compliance` の継続改修ではありません。旧リポジトリを証拠・探索資産として凍結し、検証可能な責任境界だけを選別移植するクリーンリスタートです。

## 現在の状態

- P0: `RESTART_FOUNDATION` — 完了
- P1: `SAMPLE_EXECUTION_MECHANISM` — 完了
- 現在フェーズ: `P2_INSTRUCTION_BODY_FORMATION`
- P1実装: 六つのLayer-0責任、非対称Trinity、除去監査、OFFLINE sample agent
- P1実行証拠: 保持済み25ゲームすべてでHDS承認済み1 actionと再観測の経路gateが`PASS`
- transition判断: 25件すべて保守的`SUSPEND`、`FAIL`なし（攻略実績ではない）
- 命令形保持体 `P`: **未完成・現在実装対象**
- ベンチマーク状態: **未確定**
- 満点・AGI完成・汎化達成の主張: **なし**

旧資産には `46/183`、`97/183`、`6/183` など異なる条件・時点の数値が混在しているため、新リポジトリでは同一条件の再評価が完了するまで基準値を固定しません。

## 最小設計

```text
C = Execute(L0, P)

AGI Kernel = Trinity(C, J, M)
```

- `L0`: 参照・状態条件付け・変換・候補化・放出の機能機構
- `P`: 知識、能力、関係、変換規則、パラメータを保持する命令形情報体
- `C`: `L0 + P` で成立するPure-LLM計算主体
- `J`: HDS判断主体
- `M`: HDSが引用する現行判断根拠の受動記憶主体

P1で完成したのは、`L0`側の実行責任、HDS / M権限、OFFLINE sample経路です。

現行 `PureLLMCompute` は `roles.py` の手書き規則を直接実行しており、独立した `P` をまだ使用していません。したがってP1をPure-LLM計算主体完成とは扱いません。

## 最上位目的

ARC-AGI-3 の未知タスクに対して、次の閉ループを実行できる汎用エージェントを構築します。

```text
観測
  -> 表現・状態化
  -> Layer-0が命令形保持体Pを参照・計算
  -> 複数仮説・予測・候補を生成
  -> HDSによる採否・SUSPEND・停止・rollback判断
  -> 許可された行動の放出
  -> 結果観測
  -> M更新
  -> 必要時に経験を次版Pへ明示コンパイル
  -> 再判断
```

スコア、部品数、分析ファイル数、実装量、parameter数は代替目的にしません。

## リポジトリ構造

```text
ARC-AGI-3-Agents/
  arc3_agi_agent/             Layer-0 / HDS / M / sample runtime
  README.md                   OFFLINE実行手順
  UPSTREAM_README.md          公式基盤の原README（参照専用）
  sample_main.py              OFFLINE sample runner
  agents/templates/           HDS制御sample agent
  tests/unit/                 契約・IR・機構の単体試験
  tests/integration/          sample OFFLINE境界試験
environment_files/            公式環境資産。runtime答え選択には使用しない
docs/
  architecture/
    SYSTEM_ARCHITECTURE.md
    P1_SAMPLE_EXECUTION_KERNEL.md
    P2_INSTRUCTION_BODY_FORMATION.md
  roadmap/ROADMAP.md
  migration/
  references/
vendor/wheels/                既存ベンダーwheel
```

依存関係の正本は `ARC-AGI-3-Agents/pyproject.toml` と `uv.lock` です。

## P1で実装済みの機構

`ARC-AGI-3-Agents/arc3_agi_agent/` には次があります。

- `protocol.py`: HDS判断、compute、memory、emissionの非対称権限
- `ir.py`: 観測、遷移、仮説、候補、閉包、証明義務の型付きIR
- `schema.py`: 決定論的シリアライズ、digest、runtime identity-free検査
- `verification.py`: 進捗・終端・危険・期待効果の保守的検証
- `checkpoint.py`: 証拠専用の有界checkpoint保持
- `context.py`: bounded context
- `memory.py`: HDS許可なしでは変更できない受動M
- `roles.py`: 六つのARC-native Layer-0責任の暫定callable実装
- `kernel.py`: HDS commandから結果再観測までの一循環
- `audit.py`: full setと六つのsingle-role removal
- `adapters/offline_arcade.py`: HDS承認済みactionだけを許すOFFLINE境界
- `sample_runtime.py`: action結果の再観測、検証、context / M更新

`agents/templates/layer0_sample_agent.py`と`sample_main.py`が、保持済み公式sampleを `OperationMode.OFFLINE` に固定して実行します。

P1の閉包範囲は [`docs/architecture/P1_SAMPLE_EXECUTION_KERNEL.md`](docs/architecture/P1_SAMPLE_EXECUTION_KERNEL.md) に固定しています。

## P2の現在作業

P2では、ニューラルネットワークの重み・接続・活性化条件に相当する、**Layer-0が実際に計算へ使う情報体**を形成します。

実装対象:

- `InstructionBody` interface / contract
- P-A: sampleから生成する記号・規則グラフ
- P-B: sample trajectoryから学習する小型パラメトリック／ニューラル情報体
- sample trajectory collector / identity-free dataset
- rule compiler / parameter trainer
- P version / digest / provenance
- 同一Layer-0へのP-A / P-B swap
- Pなしcompute拒否
- P / M分離
- 六責任 + P removal audit

詳細指示は [`docs/architecture/P2_INSTRUCTION_BODY_FORMATION.md`](docs/architecture/P2_INSTRUCTION_BODY_FORMATION.md) を参照してください。

## 設計上の固定境界

- ARC実行時に game/task/level ID、replay index、固定action列、answer map、literal座標表、source/hidden stateを使用しない。
- Pは計算素材を保持するが、採否・記憶確定・外部放出を独断で行わない。
- HDSは命令・採否・SUSPEND・停止・rollback・`MEMORY_WRITE`・`EXTERNAL_EMIT`許可の唯一主体とし、各command / directiveをsingle-useかつ発行実体へ束縛する。
- Mは受動的共有状態とし、許可済み命令以外で自己更新しない。
- PとMを混同しない。Mはruntime更新、Pは明示的compilerで版更新する。
- 観測されていない機構は事実へ昇格せず、仮説または `SUSPEND` として保持する。

詳細は [`docs/architecture/SYSTEM_ARCHITECTURE.md`](docs/architecture/SYSTEM_ARCHITECTURE.md) を参照してください。

## P1回帰検証

```bash
cd ARC-AGI-3-Agents
python -m compileall -q arc3_agi_agent agents tests/unit
python -m unittest discover -s tests/unit -p "test_*.py" -v
python -m pytest -q tests/unit
python -m mypy arc3_agi_agent
ruff check arc3_agi_agent agents/__init__.py agents/recorder.py tests/conftest.py tests/unit
python -m unittest discover -s tests/integration \
  -p "test_offline_sample_runner.py" -v
python sample_main.py --all-samples --max-actions 1
```

## 絶対順序

1. P0: 再起動基盤 — 完了
2. P1: Layer-0実行機構・OFFLINE sample経路 — 完了
3. P2: 命令形保持体Pの形成・接続 — 現在
4. P3: 全sample game / 全level完全攻略
5. P4: local完成状態・P/J0/M0・回帰・再現性固定
6. P5: 公式ARC実行環境へ接続
7. P6: Kaggle CLI / 公式MCP提出経路
8. P7: 全gateとユーザー許可後に実提出
9. P8: 公式評価結果を用いた最適化

P2とP3では公式API、`OperationMode.COMPETITION`、Kaggle分岐・提出、leaderboard scoreによる採否を禁止します。

[`docs/roadmap/ROADMAP.md`](docs/roadmap/ROADMAP.md) が現行ロードマップの正本です。

## Git運用

本リポジトリはローカル・リモートとも `main` だけを継続利用します。ユーザーが明示的に方針を変更しない限り、作業branchやPRは作成せず、検証済みの限定差分を `main` へ直接commit / pushします。詳細は [`AGENTS.md`](AGENTS.md) を参照してください。

## 参照と来歴

- 旧ARC実装・分析資産: `gatchimuchio/ARC-Layer-0-Functional-Compliance`
- 閉包・停止境界: `gatchimuchio/closure-phase-specs`
- Layer-0責任境界と除去監査: `gatchimuchio/LLM-Layer-0-Functional-Compliance-Specification`
- AGI三主体設計: `docs/references/AGI_Trinity_Blueprint_v0_1.md`

具体的な参照commit、採用範囲、非採用範囲は [`docs/references/SOURCE_MAP.md`](docs/references/SOURCE_MAP.md) と [`docs/migration/LEGACY_ASSET_INVENTORY.md`](docs/migration/LEGACY_ASSET_INVENTORY.md) に固定しています。
