# ARC3 Scope Lock — Current Status

rootに存在していた`PH-D00B Distillation Scope Lock`はrev3系の履歴資産であり、rev6のcurrent scopeではない。

## Current Scope

現行scopeは次の順で決まる。

1. Ownerの現在の明示指示
2. root `AGENTS.md`
3. `control/CURRENT_SELECTOR.json`
4. `control/rev6/CURRENT_TASK.json`
5. active Point指示書

現在は`R0-P01_INVALIDATE_REV5_1_FALSE_CLOSURE`であり、製品能力変更は禁止されている。

旧PH-D00Bの`distillation/`隔離境界、Python pin、Scope Guard、bridge/runtime制限は、当時の作業境界を示す履歴証拠であり、rev6のcurrent selectorではない。

## Historical Copy

rev3時点の旧文書は内容を変更せず保存する。

`docs/history/rev3_root/SCOPE_LOCK.md`

このrootファイルはcurrent scopeの誤認防止だけを目的とし、新しいrepository-wide scope lockを宣言しない。
