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

既知サンプル回帰条件:

```text
25 / 25 official sample games = WIN
183 / 183 levels = COMPLETE
one runnable product artifact
no manual per-step intervention
no fixed successful-trajectory playback
```

上位AGI正本に基づく製品完成には、さらに同一active artifactの汎用性、未使用locked evaluator完遂、package identity、公式output bytes／score／full scope完遂が必要です。既知サンプル回帰だけをAGI完成とは扱いません。

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
B-02 teacher-derived compiled product P (closed in M2)
B-03 non-compatibility product P-IR (closed in M2)
B-04 temporal action-frame/composite/history surface (closed in M1)
B-05 ACTION6 seven-class spatial candidate surface (closed in M1)
B-06 online trace exists; unknown-state capability reopened in M3
B-07 25/25 WIN, 183/183, 10,733 actions (known-sample regression)
B-08 external Kaggle write requires current Owner authorization
B-09 active product transformation 7/7、CV 0/25、active-P locked evaluation absent
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
M3_INTEGRATED_AGI_CAPABILITY
```

M0～M2と既知サンプル／package回帰は次の実測証拠で保持しています。

- `analysis/product/rev4/current_product_baseline.json`
- `analysis/product/rev4/m1_official_runtime_surface.json`
- `analysis/product/rev4/m2_product_capability_bundle.json`
- `analysis/product/rev4/m4_full_sample_product.json`
- `analysis/product/rev4/m5_clean_install_product.json`
- `analysis/product/rev4/m5_product_release.json`
- `analysis/product/rev4/product_completion_audit.json`
- M1: 25/25 initial observation、183 level契約、action 0〜7、J authorization／一手実行／再観測 25/25
- M2: FT09 75 action・6/6・WIN、同一J0／M0のP除去対照 128 action・0/6・NOT_FINISHED
- M4: 25/25 WIN、183/183 level、10,733 action、failure signature 0、shared session 1
- M5: wheel byte再現、fresh install後も25/25 WIN・183/183・10,733 action、M4との機能結果一致

wheel freeze、fresh install全数回帰、依存lock、Notebook契約は有効な回帰証拠です。active product P／J0／M0はdevelopment transformation worldを7/7完遂しました。ただしcompletion auditはCV完遂0とsealed active-P不一致を検出しており、製品完成claimを拒否しています。外部Kaggle実行と提出は、当該操作へのOwnerの現在の明示授権がある場合に限ります。

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
python scripts/build_product_completion_audit.py --check
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
