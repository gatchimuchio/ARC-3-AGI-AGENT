# Repository Operating Contract

この文書は、本repositoryでAI実装エージェント／コード監査者が作業するための**恒久的な運用契約**である。
ARC3の攻略戦略、現在Point、製品完成状態、scoreなどの可変状態はここに書かない。

目的は「作業したように見せること」ではない。
Ownerが指定した目的を保持し、正確・安全・再現可能・監査可能な変更を、因果のある最小のレビュー可能差分として実現することである。

## 1. Authority

### 1.1 規範の優先順位

1. Ownerの現在の明示指示
2. 対象pathに適用される最も近い`AGENTS.md`
3. root `AUTHORITY_ORDER.md`
4. `control/CURRENT_SELECTOR.json`が選択する現行仕様・ロードマップ・Current Task・局所指示
5. 現行コード、interface、tests、設定が示す既存契約
6. 推測、記憶、一般論

root `AGENTS.md`はrepository全体に適用する。下位`AGENTS.md`は対象subtreeをより具体化できるが、rootのauthority・evidence・failure規則を緩和してはならない。

### 1.2 規範と観測事実を混同しない

仕様書は「どうあるべきか」を定める。コード、test、runtime結果、公式結果は「何が成立しているか」を示す。

```text
Normative Target != Observed State
```

両者が矛盾する場合、文書に合わせて観測事実を読み替えない。矛盾そのものをgapとして扱い、必要なら修正対象へ戻す。

## 2. Current Stateの単一入口

可変な現在状態の入口は次だけである。

`control/CURRENT_SELECTOR.json`

作業開始時は必ずSelectorから以下を解決する。

- active strategy
- specification
- roadmap
- roadmap manifest
- Current Task
- active instruction
- auto-advance policy

README、AGENTS、architecture文書、historical artifact、過去のphase stateをCurrent Stateの代用品にしてはならない。
SelectorとCurrent Task／Manifestが不一致なら、推測で補正せずvisible failureとする。

Selectorを変更するのは、現在の作業が明示的にstate transitionを要求し、その条件を満たした場合だけである。cleanup、refactor、test PASS、artifact生成を理由に暗黙遷移しない。

## 3. 作業開始契約

変更前に次を成立させる。

1. rootと対象subtreeの`AGENTS.md`を読む。
2. `control/CURRENT_SELECTOR.json`を読み、選択された文書を解決する。
3. `python scripts/check_repository_environment.py`で環境整合を確認する。
4. 対象コード、tests、既存artifact、既知failureを確認する。
5. 「目的」「現在状態」「不足」「変更禁止範囲」を区別する。
6. 既存資産で目的を満たせないことを確認してから新規構造を作る。

既に答えがrepository内にある場合、別shell、別runner、別package、別schemaを作って同じ問題を再実装しない。

## 4. 変更原則

### 4.1 目的保持

局所的にtestを通すこと、形式を整えること、artifactを増やすことを上位目的へ昇格させない。
実装途中で既存設計が目的を阻害していると分かった場合、既存設計を守るために目的を縮小しない。

### 4.2 Root Cause First

症状だけを塞ぐ前に、再発を生む責任境界を特定する。

- state ownership
- authority drift
- stale duplication
- hidden fallback
- interface mismatch
- dependency drift
- evidence gap
- causal misattribution

が原因なら、その原因面を修正する。

### 4.3 Minimal Causal Diff

変更は小さいほど良いのではなく、**目的を成立させる因果が閉じる最小単位**にする。

- 無関係なrename、format、cleanupを混ぜない。
- 同一目的のためにparallel implementationを増やさない。
- 既存public interfaceを変更する場合はconsumerを確認する。
- path-sensitiveなrelease／Kaggle／artifact資産を見た目の整理だけで移動しない。
- generated outputをsource of truthへ昇格させない。

## 5. Evidence and Claims

主張の強さを証拠より上げない。

```text
E0  document / static structure / artifact existence
E1  unit / static / schema / deterministic local check
E2  local integrated / offline runtime result
E3  official sample environment result
E4  platform normal-run result
E5  official accepted result / score
```

上位Evidenceが必要な能力claimを、下位Evidenceで代替しない。

以下は単独では能力完成の証拠ではない。

- classやshellの存在
- test数
- schema数
- artifact数
- digest一致
- mock PASS
- package build成功
- 自己申告PASS

実行していないtestをPASSと報告しない。失敗したofficial resultをlocal成功で上書きしない。

## 6. Verification

変更後は、変更対象に最も近い検証から実行し、必要な範囲まで回帰を広げる。

1. syntax／static／targeted test
2. affected integration
3. repository／product regression
4. Current Taskが要求するofficial／platform validation

検証を通すために、gateを弱める、assertionを消す、expected resultを都合よく書き換える、例外を握り潰す、fallbackで別経路へ逃がすことを禁止する。

検証不能なものは未確認として残し、確認済みとして報告しない。

## 7. Failure Contract

失敗は隠さず、次の判断材料として保持する。

- failure evidenceを削除して成功扱いしない。
- 不明な値を推測で埋めない。
- authority／path／digest／interface不一致をsilent fallbackしない。
- generic capabilityを主張する経路にidentity routing、answer map、fixed replay等の隠れた代行を導入しない。
- 作業途中で成立不能条件が見つかった場合は、その地点と原因を明示する。

修復可能なfailureは責任componentへ戻して直す。根拠不足で先へ進めない場合は、現在地点を維持してvisible failureとして終了する。

## 8. Artifact and History

新artifactは、少なくとも次のどれかに直接使われる場合だけ作る。

- runtimeが読む
- Current／next taskが読む
- acceptance／auditが読む
- failure repairに使う
- release／submissionに必要

CURRENTとHISTORICALを混同しない。
`docs/history/`およびSelectorから選択されない旧control／旧release／旧artifactは、再利用可能な証拠ではあっても現在の権威ではない。

履歴証拠を改変して現在に合わせない。必要なら新しい訂正artifactを追加し、当時の記録を残す。

## 9. Toolchain and Dependencies

実装subtreeでは、そのsubtreeに最も近い`pyproject.toml`、lock file、`.python-version`、test設定をtoolchainの正本とする。

- dependency追加は目的上必要な場合だけ行う。
- dependencyを変更したら対応するlockを更新する。
- lock済み環境がある場合はそれを優先する。
- repository内の既存script／entrypointを確認してから新しい実行入口を作る。
- network、official access、submission等の外部副作用は、Current TaskとOwner権限の範囲でのみ実行する。

## 10. Git and Scope

- 無関係な変更をstage／commitしない。
- 変更前後のdiffを監査する。
- 一つのcommitには一つの説明可能な目的を持たせる。
- force push、history rewrite、証拠削除などの破壊的操作は明示指示なしに行わない。
- branch、commit、push、PRはそれぞれ許可された範囲だけ実行する。

## 11. Completion Report

完了報告では最低限、次を区別する。

- 何を目的に変更したか
- 何を変更したか
- 何を実行して検証したか
- 実際に観測された結果
- 未確認事項／残存risk
- Selectorを変更したか、変更していないか

「実装した」と「成立を確認した」を同義にしない。

## 12. Stable Entry Point

現在地点をこの文書へ転記しない。

```bash
python scripts/check_repository_environment.py
```

その後、`control/CURRENT_SELECTOR.json`から現在の作業を読む。
