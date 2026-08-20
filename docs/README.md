# ARC3 Document Index

このindexは文書の役割を示す。**Current Stateそのものは保持しない。**
現在の仕様・ロードマップ・Task・Instructionは[`../control/CURRENT_SELECTOR.json`](../control/CURRENT_SELECTOR.json)から解決する。

## Stable Operating Documents

- [`../AGENTS.md`](../AGENTS.md): repository-wide implementation contract
- [`../AUTHORITY_ORDER.md`](../AUTHORITY_ORDER.md): authority / observed reality / history boundary
- [`operations/REPOSITORY_OPERATING_MODEL.md`](operations/REPOSITORY_OPERATING_MODEL.md): repository operating model
- [`../control/README.md`](../control/README.md): Current Selectorとstate transitionの契約

## Upper Architecture / References

- [`architecture/AGI三主体統合設計正本_v0_2.md`](architecture/AGI三主体統合設計正本_v0_2.md): 上位AGI責任構造
- [`references/HDS_FRAMEWORK_rev3_1a_INTERNAL.md`](references/HDS_FRAMEWORK_rev3_1a_INTERNAL.md): HDS内部仕様
- [`references/HDSフレーム_rev3_1_外向け仕様.md`](references/HDSフレーム_rev3_1_外向け仕様.md): HDS外向け仕様

これらの文書は上位構造を与えるが、Current Pointや能力成立を宣言するstate fileではない。

## Strategy Documents

`strategy/`には複数世代の戦略仕様が共存する。
**ファイル名のrev番号やmtimeではなくSelectorの`spec_path`だけが現行仕様を選ぶ。**

## Roadmaps

`roadmap/`には複数の実装ロードマップが存在する。
現行ロードマップはSelectorの`roadmap_path`から解決する。
ロードマップ上のPoint存在は、そのPointの実装完了証拠ではない。

## Instructions

`instructions/`は局所作業契約を保持する。
実行対象はSelectorの`current_task_path`と`active_instruction_path`から一意に選ぶ。
旧Instructionを近い名前という理由だけで実行しない。

## Evaluation / Official / Security / Audit

- `evaluation/`: 評価役割・境界
- `official/`: official completion predicates等
- `security/`: identity／taint等のsecurity boundary
- `audit/`, `audits/`: 監査記録・監査仕様
- `migration/`: 過去資産の分類・移行記録

これらは現在Taskの入力になり得るが、自身でCurrent Stateを選択しない。

## History

[`history/README.md`](history/README.md)は、旧authority／旧release／旧submission等を現在の権威面から分離するindexである。

旧文書は削除しない。ただしSelectorから選択されない限りcurrent authorityではない。

## Document Rules

1. Current ID、score、product statusをstable indexへ複製しない。
2. 仕様上のclaimと実測結果を同じものとして書かない。
3. historical documentを現在に合わせて改変しない。
4. 新しい文書はruntime、Task、audit、failure repair、release等の直接consumerがある場合に作る。
5. current entrypointを増やさない。Currentは`control/CURRENT_SELECTOR.json`から始める。
