# ARC-3 AGI Agent

ARC Prize 2026 / ARC-AGI-3向けの、**未知環境を観測し、命令形保持体をLayer-0で計算し、HDSの判断を経て行動する汎用エージェント**の新規実装リポジトリです。

本リポジトリは `gatchimuchio/ARC-Layer-0-Functional-Compliance` の継続改修ではありません。旧リポジトリを証拠・探索資産として凍結し、検証可能な責任境界だけを選別移植するクリーンリスタートです。

## 現在の状態

- P0: `RESTART_FOUNDATION` — 完了
- P1: `SAMPLE_EXECUTION_MECHANISM` — 完了
- P2: `AGI_MINIMUM_THREE_AUDIT` — 完了
- P3: `ARC3_EVIDENCE_MATERIAL_COMPILER` — 完了
- 現在フェーズ: `P4_COMPUTE_SUBJECT_C`
- P1実装: 六つのLayer-0責任、非対称Trinity、除去監査、OFFLINE sample agent
- P1実行証拠: 保持済み25ゲームすべてでHDS承認済み1 actionと再観測の経路gateが`PASS`
- transition判断: 25件すべて保守的`SUSPEND`、`FAIL`なし（攻略実績ではない）
- 命令形保持体 `P`: **未完成・P4実装対象**
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
  arc3_agi_agent/             Layer-0 / HDS / M / sample runtime / evidence compiler
  README.md                   OFFLINE実行手順
  UPSTREAM_README.md          公式基盤の原README（参照専用）
  sample_main.py              OFFLINE sample runner
  agents/templates/           HDS制御sample agent
  tests/unit/                 契約・IR・機構の単体試験
  tests/integration/          sample OFFLINE境界試験
environment_files/            公式環境資産。runtime答え選択には使用しない
datasets/                     P3 identity-free C/J/M fixture
manifests/                    P3 dataset/provenance/identity audit
docs/
  architecture/
    AGI_MINIMUM_THREE_SPEC.md
    AGI_OBLIGATION_GRAPH.json
    AGI_TRACEABILITY_MATRIX.md
    AGI_CLAIM_REGISTRY.md
    AGI_TEST_MATRIX.md
    AGI_CURRENT_IMPLEMENTATION_AUDIT.md
    SYSTEM_ARCHITECTURE.md
    P1_SAMPLE_EXECUTION_KERNEL.md
    P3_ARC3_EVIDENCE_MATERIAL_COMPILER.md
    P4_COMPUTE_SUBJECT_IMPLEMENTATION.md
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

## P2根本監査・P3実証素材とP4の現在作業

P2ではG1〜G5、C/J/M、L0/P、environment、compiler、P0/J0/M0、
全8部分集合を一対一で監査し、未実装を完成扱いしないclaim/test境界を固定しました。

- [`AGI最小三構成仕様`](docs/architecture/AGI_MINIMUM_THREE_SPEC.md)
- [`現行実装根本監査`](docs/architecture/AGI_CURRENT_IMPLEMENTATION_AUDIT.md)
- [`義務graph`](docs/architecture/AGI_OBLIGATION_GRAPH.json)

P3では730/730 sourceをaccountingし、5,047件のidentity-free
observation / transition / effect / hazard / progress / contradiction corpus、
HDS Frame fixture、memory lifecycle fixtureへ変換しました。source identity漏洩は
0件、全12生成物の再buildはbyte一致です。完了証拠は
[`P3_ARC3_EVIDENCE_MATERIAL_COMPILER.md`](docs/architecture/P3_ARC3_EVIDENCE_MATERIAL_COMPILER.md)
に固定しています。

現在のP4では、このfixtureをruntime identity-free境界内で使用し、P-A/P-Bと
standalone Cを実装します。実装仕様は
[`P4_COMPUTE_SUBJECT_IMPLEMENTATION.md`](docs/architecture/P4_COMPUTE_SUBJECT_IMPLEMENTATION.md)
です。

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
3. P2: AGI最小三構成仕様・根本監査 — 完了
4. P3: ARC3実証素材compiler — 完了
5. P4: 計算主体C — 現在
6. P5: 判断主体J
7. P6: 記憶主体M
8. P7: 二主体接続監査
9. P8: 三主体二周期循環
10. P9: 全8部分集合証明
11. P10: 全sample game / 全level完全攻略
12. P11: release state固定

P11完了前は公式API、`OperationMode.COMPETITION`、Kaggle分岐・提出を禁止します。

現行ロードマップ全文の正本は
[`AGI_MINIMUM_THREE_IMPLEMENTATION_PROOF_ROADMAP.md`](docs/roadmap/AGI_MINIMUM_THREE_IMPLEMENTATION_PROOF_ROADMAP.md)
です。

## Git運用

本リポジトリはローカル・リモートとも `main` だけを継続利用します。ユーザーが明示的に方針を変更しない限り、作業branchやPRは作成せず、検証済みの限定差分を `main` へ直接commit / pushします。詳細は [`AGENTS.md`](AGENTS.md) を参照してください。

## 参照と来歴

- 旧ARC実装・分析資産: `gatchimuchio/ARC-Layer-0-Functional-Compliance`
- 閉包・停止境界: `gatchimuchio/closure-phase-specs`
- Layer-0責任境界と除去監査: `gatchimuchio/LLM-Layer-0-Functional-Compliance-Specification`
- AGI三主体設計: `docs/references/AGI_Trinity_Blueprint_v0_1.md`

具体的な参照commit、採用範囲、非採用範囲は [`docs/references/SOURCE_MAP.md`](docs/references/SOURCE_MAP.md) と [`docs/migration/LEGACY_ASSET_INVENTORY.md`](docs/migration/LEGACY_ASSET_INVENTORY.md) に固定しています。
