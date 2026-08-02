# ARC3 Completion AGI Agent

ARC Prize 2026 / ARC-AGI-3公式サンプルを、**同一のC／J／M／P構造で自律完遂する製品`ARC3CompletionAgent`**を構築するrepositoryです。

## 最終成果物

```text
ARC3CompletionAgent
=
official adapter
+ C = Execute(L0, P)
+ HDS judgement subject J
+ mutable memory subject M
+ product runtime
+ ARC3 product capability bundle
```

HDS分析、成功軌道、解析データ、汎用構造、命令形Pは製品能力を構築する素材・手段・内部部品です。これらを作っただけでは開発完了ではありません。

開発完了条件:

```text
25 / 25 official sample games = WIN
183 / 183 levels = COMPLETE
one runnable product artifact
no manual per-step intervention
no fixed successful-trajectory playback
```

## 現行正本

- [製品仕様書 rev4](docs/strategy/ARC3_AGIエージェント_製品仕様書_rev4.md)
- [製品開発ロードマップ rev4](docs/roadmap/ARC3_AGIエージェント_製品開発ロードマップ_rev4.md)
- [Codex製品開発契約](AGENTS.md)
- [Current Product Task](control/rev4/CURRENT_TASK.json)
- [rev4 governance contract](docs/strategy/contracts/REV4_PRODUCT_GOVERNANCE_CONTRACT_V1.json)

旧rev3のHDS蒸留多段工程、P0〜P22、S0〜S6は履歴・再利用資産であり、現在の開発endpointではありません。

## 公式サンプルと保持済み素材

```text
official games                    25
official levels                   183
PH-D05 canonical frames           10,942
PH-D05 canonical success actions  11,574
max known success actions/game    1,519
supported actions                 RESET, ACTION1..ACTION7
```

## 現行製品候補

既存repositoryには次の製品部品があります。

- `GenericAGIAgent`: official Agent shell
- `GenericAGIRuntime`: C／J／M／P循環
- `CognitiveSession`: run単位の継続主体
- `GenericHDSJudgementSubject`: action／memory／rollback権限
- `SemanticMemory`: 可変判断根拠
- `CompetitionGenericEnvironment`: official adapter
- `generic_competition_runner`: 25 game逐次runner
- typed P-IR／interpreter／compiler

これらを捨てず、`ARC3CompletionAgent`製品へ統合します。

## 確認済みの製品阻害要因

```text
B-01 product path budget = 4096 >= known max 1519 (closed in product path)
B-02 active P is generic exploration/scoring only
B-03 default P-IR is a compatibility fixture
B-04 temporal action-frame/composite/history surface (closed in M1)
B-05 ACTION6 seven-class spatial candidate surface (closed in M1)
B-06 goal/mechanism/subgoal/plan induction is incomplete
B-07 all-25 bounded product baseline (closed in M0)
```

## 製品開発ロードマップ

1. `M0_PRODUCT_BASELINE_AND_BLOCKER_CLOSURE`
2. `M1_OFFICIAL_PRODUCT_RUNTIME`
3. `M2_PRODUCT_CAPABILITY_BUNDLE`
4. `M3_INTEGRATED_AGI_CAPABILITY`
5. `M4_FULL_SAMPLE_REPAIR_LOOP`
6. `M5_PRODUCT_CLOSURE_AND_PACKAGING`

全milestoneで実行可能な`ARC3CompletionAgent`を保持し、公式サンプル上の実測差分を出します。

## 現在作業

```text
M2_PRODUCT_CAPABILITY_BUNDLE
```

M0／M1は次の実測証拠で閉じています。

- `analysis/product/rev4/current_product_baseline.json`
- `analysis/product/rev4/m1_official_runtime_surface.json`
- M1: 25/25 initial observation、183 level契約、action 0〜7、J authorization／一手実行／再観測 25/25

現在は教師・HDS素材を、製品runtimeが直接loadする`P／J0／M0` bundleへコンパイルします。分析artifactだけを独立完成させません。

公式sampleを使う現行製品入口（既定は全25 game、OFFLINEのみ）:

```bash
cd ARC-AGI-3-Agents
python -m arc3_agi_agent.product_runner \
  --mode offline \
  --action-budget 4096 \
  --report ../analysis/product/rev4/current_product_baseline.json
```

`--game LS20`のような部分実行はadapter診断専用で、M0 baselineまたは製品完成には数えません。

M1公式runtime surfaceの再現コマンド:

```bash
cd ARC-AGI-3-Agents
python scripts/run_m1_official_runtime_surface_acceptance.py \
  --output ../analysis/product/rev4/m1_official_runtime_surface.json
```

## 現在gate

```bash
python scripts/validate_rev4_product_governance.py
cd ARC-AGI-3-Agents
python -m pytest -q tests/unit/test_product_runner.py tests/unit/test_product_governance.py
```

`control/rev3/REV3_CURRENT_SELECTOR.json`はpath名を変更せず履歴保存していますが、現在selectorではありません。

## 製品進捗指標

```text
games started
games WIN
levels completed
failure classes
actions used
resource stops
memory-caused behavior changes
regressions
```

test数、schema数、artifact数、commit数は製品完成の代替指標にしません。
