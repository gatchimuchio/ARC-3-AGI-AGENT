# 旧ARC3資産 棚卸し・移植判断

- 移植元: `gatchimuchio/ARC-Layer-0-Functional-Compliance`
- 監査基準commit: `0970dc6a56addf2f2ca494efbf80ef919e2e3a12`
- 移植先: `gatchimuchio/ARC-3-AGI-AGENT`
- 判断日: 2026-07-23

## 1. 結論

旧リポジトリは、コード、ARC2、ARC3、分析生成物、task別route、replay、複数のHDS/Trinity実装、score履歴が同居しており、新系の基礎として一括継承しません。

扱いは次の通りです。

```text
旧repo = 凍結された探索・証拠・失敗資産
新repo = 正式な再実装・統合・検証資産
```

## 2. 規模と汚染指標

確認できた事実:

- 初期scaffoldから監査commitまで約1,677 commits
- `analysis/` のJSON inventory: 657件
- stale score artifact: 233件
- 183 levelの形式inventoryは存在
- unresolved level: 107
- HDS SUSPEND / open proof obligation: 126
- open required evidence items: 504
- old `agent/my_agent.py`: 約19,299行

数値正本も一致していません。

| 資産 | 記録値 | 条件・問題 |
|---|---:|---|
| `analysis/arc3_local_score_oracle_latest.json` | 46 / 183 | generic-only、RHAE 16.113997114% |
| 旧AGENTS / roadmap | 97 / 183 | 別時点のbenchmark anchor |
| completion audit | current public 6 / 183 | phase entry 76から-70 |

したがって、新repoでは過去scoreをbaselineとして採用しません。

## 3. ADAPT — 初回移植

| 旧path | 旧blob SHA | 新path | 判断 |
|---|---|---|---|
| `agent/trinity_protocol.py` | `e51083bc8744730b93056f5a562c59e8aea35b4d` | `ARC-AGI-3-Agents/arc3_agi_agent/protocol.py` | 非対称権限と状態機械を簡素化して移植 |
| `agent/arc3_ir/types.py` | `27f916cfd7160f9dc8a191bf256badd52c07bc4c` | `.../ir.py` | task identity-freeな型を中心に移植 |
| `agent/arc3_ir/schema.py` | `69dfa4e52dde6dccede79162e324c7bfc3f70562` | `.../schema.py` | canonical JSON、digest、runtime検査を移植 |
| `agent/hds_verifier/verifier.py` | `1bc8563a16bb78d0de4da515d68543aaf7b38ded` | `.../verification.py` | rendered evidence限定を明示し保守化 |
| `agent/hds_verifier/checkpoint.py` | `5e847a4f9812af614ecfccac521eb1b0e31df25c` | `.../checkpoint.py` | 環境復元ではなく証拠保持として移植 |

変更原則:

- 旧package依存を除去
- game ID / replay indexをactive型から除去
- `NO_HAZARD_OBSERVED` を安全証明へ昇格しない
- external APIなしで単体試験可能にする
- runtime接続は別phaseとする

## 4. REFERENCE — 設計・証拠のみ

| 資産 | 利用範囲 | 非採用理由 |
|---|---|---|
| `ARC3_WORK_CONTROL.md` | 目的、禁止入力、HDS循環 | 旧path、旧phase、旧score条件を含む |
| `ARC3_HDS_LAYER0_MAXIMUM_AGENT_AUTHORITY.md` | 六責任、除去証人、非対称権限 | 現行実装評価と旧repo固有記述を含む |
| `AGENTS.md` | work block、証拠、failure分類 | 旧branch/path、+1 score gateを含む |
| `analysis/arc3_agi_agent_complete_implementation_roadmap.md` | Phase A–Fの順序 | 旧repo前提、97/183前提を含む |
| `analysis/arc3_full_task_analysis_completion_audit_latest.json` | 未解決数、stale inventory | 巨大な生成物正本でありtask selectorにしない |
| `analysis/arc3_local_score_oracle_latest.json` | 過去の比較資料 | generic-only条件で新baselineではない |
| `agent/trinity_state.py` | 抽象・構造・認知の分離 | game ID / replay indexをframeに保持 |
| `agent/arc3_ir/normalize.py` | feature正規化の着想 | 旧analysis schemaとkeyword heuristicへ密結合 |
| `agent/hds_verifier/rollback.py` | rollback adapterの着想 | verifier PASSとundo許可の意味が過結合 |
| `agent/hds_verifier/plan_search.py` | bounded planの着想 | 旧candidate surfaceへ依存 |

## 5. QUARANTINE — 比較・失敗解析専用

| 資産 | 理由 |
|---|---|
| `agent/my_agent.py` | game-ID router、replay table、task別action pathが中心 |
| `agent/hds_layer0_maximum_runtime.py` | 部分的な汎用基盤はあるが巨大で旧runtimeと密結合 |
| `agent/trinity_runtime.py` | 複数世代の責任衝突と旧呼出経路を含む |
| `agent/pure_llm/*` | 素材・memory・bridgeが分散し、active pathとshadow pathが混在 |
| `agent/hds_actuation/*` | 旧candidate、failure memory、外周auditへ密結合 |
| task別policy / replay / route assets | 新coreへの流入を禁止する必要がある |

Quarantine資産は、新実装とのA/B比較や失敗署名抽出には利用できますが、import・fallback・自動routeを禁止します。

## 6. REJECT — 新系へ移さないもの

- `analysis/*` の一括コピー
- stale score artifact
- ARC2領域
- 絶対Windows/WSL path
- 旧branch名、旧worktree前提
- task/game/level IDによるaction選択
- replay-index lookup
- 固定action列、literal coordinate、answer map
- source/hidden stateのruntime利用
- metadataラベルだけのHDS/Layer-0適合主張
- 同一条件評価なしのscore claim

## 7. 移植先に既に存在する資産

### 公式基盤

`ARC-AGI-3-Agents/` は公式runner・agent base・tests・dependency lockとして保持します。新coreは当面、独立packageとして追加し、公式実行pathは変更しません。

### 環境資産

`environment_files/` は25 gameのsource/metadataを含みます。解析・ローカル再現・テストfixtureとしてのみ扱い、solver runtimeの答え選択には使いません。

### wheel群

ルート直下のwheel群はベンダー資産として `HOLD` します。

理由:

- binary moveは内容同一性と依存lockの監査が必要
- 現PRの目的はアーキテクチャ基盤であり、依存物再配置を混ぜない
- 将来、`vendor/wheels/` または外部artifact管理へ移す別PRを作る

## 8. 次回移植候補

P1で個別監査する候補:

- object / relation / delta抽出の小型純関数
- candidate provenance型
- bounded memory lifecycle
- failure signature compression
- replay quarantine gate
- single-role removal audit harness

採用条件:

1. task identity-free
2. external APIなし
3. 入出力・状態所有者が明示
4. 単体試験可能
5. 除去時の機能喪失を説明可能
6. HDS権限境界を迂回しない
