# Control Plane

`control/`は、repositoryの可変な実行状態を扱う。

## Current Entry Point

現在の作業を選択する唯一の入口はrootの

`control/CURRENT_SELECTOR.json`

である。

version別directory、旧phase state、approval record、artifact-local `next_*`は、Selectorから選択されない限りcurrentではない。

## Selector Contract

Selectorは少なくとも次を解決する。

- `active_strategy`
- `spec_path`
- `roadmap_path`
- `roadmap_manifest_path`
- `current_task_path`
- `active_point`
- `active_instruction_path`
- `auto_advance_allowed`

参照pathはrepository-relative POSIX pathとし、`docs/history/`やhistorical namespaceを選択しない。

## Mirror State

Current TaskやRoadmap Manifestにstrategy／Point／auto-advance等の同値が記録されている場合、それらは**Selectorとの整合確認用mirror**として扱う。

```text
Selector != mirror
=> STATE_DRIFT / visible failure
```

mtime、ファイル名のrev番号、過去のapproval数などでどちらが正しいかを自動推定しない。

## Transition Rule

Selector更新は通常の実装変更とは別のstate transitionである。

- exit条件を満たしただけでは自動遷移しない。
- `auto_advance_allowed`とCurrent Taskの権限を確認する。
- transition時はSelectorと必要なmirrorを同一変更で整合させる。
- historical stateを上書きして現在化しない。

## Validation

```bash
python scripts/check_repository_environment.py
```

このcheckは、Selector参照先の存在、strategy／Point／instruction／auto-advanceのmirror一致、stable文書へのCurrent ID複製を監査する。
