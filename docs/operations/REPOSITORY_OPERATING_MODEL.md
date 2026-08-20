# Repository Operating Model

この文書はARC3攻略戦略ではなく、repository自体を長期運用するための環境設計を説明する。
規範上の実行契約はroot `AGENTS.md`、権威順序はroot `AUTHORITY_ORDER.md`を正本とする。

## 1. 設計目的

このrepositoryでは、戦略・実装・検証・履歴が長期間にわたり更新される。
そのため、同じ「現在」を複数のREADMEやphase文書へ転記すると、必ずstate driftが発生する。

環境設計の目的は次の四つ。

1. AI実装者が「今何をするか」を一意に解決できること。
2. 仕様上の期待と実際の能力を混同しないこと。
3. 古い資産を削除せず、現在の権威から分離すること。
4. 戦略を更新してもrepository operating contractを作り直さなくてよいこと。

## 2. Four Planes

### A. Normative Plane

「何を目指し、何を守るか」を定義する。

```text
Owner instruction
→ AGENTS.md
→ AUTHORITY_ORDER.md
→ upper architecture / HDS
→ selector-selected specification / roadmap / task / instruction
```

ここでは能力が実際に成立したとは主張しない。

### B. Selection Plane

「今どれを実行するか」を選択する。

```text
control/CURRENT_SELECTOR.json
```

Selectorだけがcurrent entrypointである。
Current TaskやRoadmap Manifestのstate値は整合確認用のmirrorであり、独立selectorではない。

### C. Evidence Plane

「何が実際に成立したか」を観測する。

```text
source / tests / runtime trace / local result / official result / platform result / score
```

文書上の完成宣言より、直接観測されたfailureを優先する。

### D. Historical Plane

「以前何が起きたか」を保存する。

```text
docs/history/
old strategy / roadmap / control
old release / submission / claim / evidence
```

履歴は再利用できるが、現在を選択できない。

## 3. Single Source of Current Work

Current Workを知るためにREADMEを探索しない。

```text
control/CURRENT_SELECTOR.json
├ spec_path
├ roadmap_path
├ roadmap_manifest_path
├ current_task_path
├ active_point
├ active_instruction_path
└ auto_advance_allowed
```

Selectorの参照先はrepository-relative POSIX pathとし、historical namespaceを指してはならない。

Current TaskやManifestにもPoint等が記録されている場合は、Selectorと完全一致して初めて有効なmirrorとみなす。
不一致時は多数決やmtimeで正解を推定しない。

## 4. Work Resolution

一回の作業は次の流れで解決する。

```text
Owner objective
↓
Repository Operating Contract
↓
Current Selector
↓
Selected Task / Instruction
↓
Observed implementation and evidence
↓
Target - Current = Gap
↓
Minimal causal change
↓
Relevant verification
↓
Observed result
↓
Report / explicit state transition when authorized
```

重要なのは、Taskより先に実装を始めないことと、実装後に結果を仕様から推定しないことである。

## 5. Claim / Evidence Boundary

repository内のclaimは、直接対応するevidence levelを越えない。

| Level | Evidence | 許される主張の例 |
|---|---|---|
| E0 | 文書・静的構造・artifact存在 | 定義済み、生成済み、構造あり |
| E1 | unit/static/schema/local deterministic check | 局所契約を満たす |
| E2 | local integrated/offline runtime | ローカル統合経路で成立 |
| E3 | official sample environment | 公式sample環境で観測 |
| E4 | platform normal run | platform実行成立 |
| E5 | accepted official result / score | 公式結果として成立 |

E0〜E2をE5の代用にしない。

## 6. Directory Semantics

### `control/`
Current Selectorとstrategy-specific state。現在の入口はroot selectorだけ。

### `docs/architecture/` / `docs/references/`
上位構造・HDS等。戦略より上の責任境界を記述する。

### `docs/strategy/`
目的に対する攻略設計。Currentかどうかはファイル名ではなくSelectorで決まる。

### `docs/roadmap/`
戦略を実装順へ射影する。進捗の事実そのものではない。

### `docs/instructions/`
局所作業契約。Selectorから現在Taskを経由して選択する。

### `ARC-AGI-3-Agents/`
product implementation。subtreeのtoolchainとローカルAGENTSに従う。

### `analysis/` / `evidence/` / `artifacts/`
観測・評価・生成物。存在するだけではCurrent Authorityやcompletionにならない。

### `release/` / `kaggle_notebooks/`
release／platform資産。現行性は名前で推測しない。

### `docs/history/`
明示的historical index。現在の選択面から隔離する。

## 7. Anti-Drift Rules

次を禁止する。

- active PointをREADME／AGENTSへコピーする。
- scoreを仕様書の完成状態へ転記して以後の事実確認を省略する。
- 過去の`CURRENT_TASK.json`をmtimeだけでcurrent扱いする。
- 古いcompletion artifactを新releaseの親へ暗黙採用する。
- test PASSをofficial capabilityへ昇格させる。
- cleanupを理由に実行pathを無監査で移動する。

`python scripts/check_repository_environment.py`は、特にSelector参照・mirror一致・stable surfaceへのCurrent ID重複を監査する。

## 8. State Transition

State transitionは通常の実装変更とは別の作用である。

1. Current Taskのexit条件を観測する。
2. 必須evidenceを固定する。
3. transition権限を確認する。
4. Selectorと必要なmirrorを同一変更で更新する。
5. environment checkerで整合を確認する。

`auto_advance_allowed = false`なら、exit条件を満たしてもSelectorを自動更新しない。

## 9. Environment Changes

AGENTS、authority model、Selector schema、directory semantics、toolchain等の環境変更は、攻略戦略の変更と分離する。

環境変更だけのcommitでは原則としてproduct capability、strategy、score claimを変更しない。
これにより、環境改善の結果を攻略成果と誤認しない。
