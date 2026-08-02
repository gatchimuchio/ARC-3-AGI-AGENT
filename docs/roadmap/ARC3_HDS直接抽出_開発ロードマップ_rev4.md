# ARC3 HDS直接抽出 開発ロードマップ rev4

- Roadmap ID: `ARC3_HDS_DIRECT_EXTRACTION_ROADMAP_REV4`
- 対象repository: `gatchimuchio/ARC-3-AGI-AGENT`
- 上位仕様: `docs/strategy/ARC3_HDS直接抽出_汎用構造命令形P_実装仕様書_rev4.md`
- 日付: `2026-08-02`
- 状態: `OWNER_DIRECTIVE_INSTALLED`
- 現在phase: `P1_TASK_DECOMPOSITION`
- 旧rev3 roadmap: `HISTORICAL_SUPERSEDED`

---

## 0. 完成までの一本道

```text
P1 全183 levelをHDSでタスク分解
  ↓
P2 同型を統合しARC3汎用構造を抽出
  ↓
P3 汎用構造を命令形Pへコンパイル
  ↓
P4 Pを同一ARC3エージェントへ接続
  ↓
P5 全183 level実行・失敗分類・修正循環
  ↓
P6 公式artifact化・提出・結果監査
```

別Track、Bridge専用Track、証拠専用Track、承認専用Trackは作らない。

---

# P1 — TASK DECOMPOSITION

## 目的

25 game／183 levelの成功軌道を、HDSで「状態・対象・関係・条件・操作・効果・目的・失敗」へ分解する。

## 入力

- PH-D05 canonical teacher trajectories
- raw recording
- before／after frames
- action／payload
- available actions
- progress／terminal／reset
- 既知回答・成功行動列

## 実装

1. 全183 levelを列挙する。
2. 各levelのterminal／goalを確定する。
3. 成功軌道をstepへ分割する。
4. 各stepから次を抽出する。
   - before state
   - entity／role
   - relation
   - precondition
   - selected target
   - operation
   - immediate effect
   - delayed effect
   - progress contribution
   - hazard／failure alternative
5. terminalから逆向きに寄与関係を結ぶ。
6. `TaskDecompositionRecord`を出力する。
7. 抽出不能項目は推測で埋めず`open_terms`へ置く。

## 必須成果物

```text
distillation/artifacts/decomposition/arc3/rev4/manifest.json
distillation/artifacts/decomposition/arc3/rev4/cases/*.json.gz
distillation/artifacts/decomposition/arc3/rev4/report.json
```

## テスト

- 25 game／183 levelが一意に存在する
- 全成功stepが一つの分解記録へ所属する
- orphan action = 0
- before／action／afterの参照が閉じる
- terminal contributionを追跡できる
- round-tripで元軌道へ対応づけられる

## Exit

```text
TASK_DECOMPOSITION_COMPLETE
```

---

# P2 — GENERIC STRUCTURE EXTRACTION

## 目的

P1の分解記録から、game固有表現を除いた再利用可能な構造を抜く。

## 実装

1. 全分解記録をStructureAtomへ変換する。
2. 対象名、色、絶対座標、action IDをparameter候補へ分離する。
3. 入力責任、条件、操作、効果、目的が同型のAtomをfamilyへ統合する。
4. 各familyへpositive／negative／near-miss／failure例を付与する。
5. wrong-target／wrong-order／wrong-effect等の反対構造を作り、境界を確定する。
6. case固有残差を明示し、無理に統合しない。
7. GenericStructureLibraryを出力する。

## 必須成果物

```text
distillation/artifacts/structures/arc3/rev4/library.json
distillation/artifacts/structures/arc3/rev4/families/*.json
distillation/artifacts/structures/arc3/rev4/case_mappings.jsonl
distillation/artifacts/structures/arc3/rev4/report.json
```

## テスト

- 全TaskDecompositionRecordがfamilyまたはcase-specific residueへ対応する
- 同一family内でlogic／parameterが分離される
- game IDだけのfamily分岐がない
- fixed trajectoryを保存するfamilyがない
- positive／negative例により境界を説明できる

## Exit

```text
GENERIC_STRUCTURE_LIBRARY_COMPLETE
```

---

# P3 — IMPERATIVE P COMPILATION

## 目的

P2の汎用構造を、Layer-0が実行できる命令形保持体Pへ変換する。

## 実装

1. StructureFamilyをImperativePRecordへ変換する。
2. applicability／observation／selector／precondition／operation／effect／verification／hazard／failure updateを型付けする。
3. 既存IR／interpreterへ接続する。
4. runtime観測からparameter bindingを作るGameBinding契約を実装する。
5. PBundleを生成する。
6. 既知step上でPの予測と観測効果を照合する。

## 必須成果物

```text
distillation/artifacts/p/arc3/rev4/p_bundle.json
distillation/artifacts/p/arc3/rev4/type_registry.json
distillation/artifacts/p/arc3/rev4/operator_registry.json
distillation/artifacts/p/arc3/rev4/coverage.json
```

## テスト

- 全active familyがPへコンパイルされる
- 全Pがtype-check／execute可能
- 全Pにeffect verificationとfailure updateがある
- game ID／trajectory lookup／answer mapを含まない
- 同じPへ異なるGameBindingを与えられる

## Exit

```text
ARC3_IMPERATIVE_P_BUNDLE_COMPLETE
```

---

# P4 — AGENT INTEGRATION

## 目的

PBundleを既存のC／J／M／Trinity substrateへ接続し、同一agentが観測からPを選択・実行できる状態にする。

## 実装

1. active PBundleを一つに固定する。
2. Cが観測とMから適用可能Pを検索する。
3. CがGameBinding、候補action、予測effect、probeを生成する。
4. JがHDSで採否し、一actionだけ外部へ送る。
5. Mが支持、反証、失敗、progress、bindingを更新する。
6. reobserve後にeffect attributionを行う。
7. WAIT／PROBE／ROLLBACK／RESET／STOPを実装する。

## 必須成果物

```text
ARC-AGI-3-Agents/arc3_agi_agent/structure_library.py
ARC-AGI-3-Agents/arc3_agi_agent/p_bundle.py
ARC-AGI-3-Agents/arc3_agi_agent/generic_agent.py
ARC-AGI-3-Agents/tests/integration/test_rev4_generic_agent.py
```

## テスト

- 全external actionがJ承認を通る
- relevant M変更で候補または行動が変化する
- irrelevant M追加で行動が変化しない
- Pなし、bindingなし、effect不一致で安全にSUSPENDする
- game ID router／fixed sequence／full-state lookupがない

## Exit

```text
GENERIC_AGENT_P_CONNECTED
```

---

# P5 — FULL EXECUTION REPAIR LOOP

## 目的

同一agentで全25 game／183 levelを実行し、失敗をHDSで分類して、構造・P・J・Mの必要箇所だけを修正する。

## 循環

```text
RUN
→ OBSERVE FAILURE
→ CLASSIFY
→ LOCATE RESPONSIBILITY
→ PATCH MINIMUM RESPONSIBLE ARTIFACT
→ REGRESSION
→ RUN AGAIN
```

## 失敗分類

```text
OBSERVATION_MISSING
REPRESENTATION_ERROR
ENTITY_ROLE_ERROR
RELATION_ERROR
PRECONDITION_ERROR
OPERATION_ERROR
EFFECT_MODEL_ERROR
DELAY_ATTRIBUTION_ERROR
GOAL_ERROR
HAZARD_ERROR
ORDER_ERROR
P_APPLICABILITY_ERROR
BINDING_ERROR
JUDGEMENT_ERROR
MEMORY_ERROR
RESOURCE_ERROR
```

## 修正先

| Failure | 主修正先 |
|---|---|
| 観測・表現・対象・関係 | P1／P2 |
| 条件・操作・効果・順序 | P2／P3 |
| applicability／binding | P3／P4 |
| 採否・probe・rollback | P4 J |
| 支持・反証・履歴 | P4 M |
| resource | runtime budget |

## 必須成果物

```text
control/rev4/FAILURE_LOG.jsonl
control/rev4/COMPLETION_STATUS.json
analysis/rev4/full_execution_report.json
```

## 完成条件

```text
25/25 game complete
183/183 level complete
crash = 0
unbounded retry = 0
regression failure = 0
```

既知公開群の183/183を達成しても、未知汎化または公式private完遂とは呼ばない。

## Exit

```text
PUBLIC_183_COMPLETE
```

---

# P6 — OFFICIAL PACKAGING AND EVALUATION

## 目的

P5で閉じた同一artifactをKaggle環境へ配置し、提出契約と実行経路を確認する。

## 実装

1. dependency／wheel／entrypointを固定する。
2. Kaggle Notebookを生成する。
3. placeholder output、Arrow型、列順、保存先を検証する。
4. offline smokeを実行する。
5. Kaggle normal runを実行する。
6. 同じartifactを提出する。
7. system errorとagent errorを分離記録する。

## 完成条件

```text
same artifact packaged
normal run complete
submission accepted
official result observed
```

## Exit

```text
OFFICIAL_RESULT_OBSERVED
```

---

## 運用規則

### 現在作業

```text
P1_TASK_DECOMPOSITION
```

Ownerの追加承認を待たず、P1内の実装・試験・修正を継続する。次phaseへ進む条件は前phaseのExitだけである。

### 禁止

- 新repository作成
- roadmap外の新Track作成
- schema／証拠／承認だけのphase追加
- 次工程が読まないartifactの量産
- P1完了前のP3／P4先行実装
- PBundle完成前の提出最適化
- 目的をHDS理論証明へ変更すること

### 成果物制限

各phaseのprimary artifactは一系統、verification reportは一つまでを原則とする。次工程が読まないartifactは作らない。
