# ARC3 Dependency Lock — Current Status

rootに存在していた`PH-D00A HDS Dependency Lock`はrev3系の履歴資産であり、rev6のrepository-wide dependency freezeではない。

## Current Rule

- 現行strategyはrev6。
- 現在の依存関係は、`AGENTS.md`、`control/CURRENT_SELECTOR.json`、`control/rev6/CURRENT_TASK.json`、active Point指示書の境界で扱う。
- **rev6全体のrelease dependency freezeはまだ成立していない。**
- release用のcode／dependency／resource freezeは、rev6 roadmapの`M4-P02_CODE_DEPENDENCY_RESOURCE_FREEZE`で初めて成立対象になる。
- 旧PH-D00A lock、旧digest、旧Translator固定commitをrev6の完成・release・現在依存の証拠へ昇格させない。

## Historical Copy

rev3時点の旧文書は内容を変更せず保存する。

`docs/history/rev3_root/DEPENDENCY_LOCK.md`

このrootファイルはcurrent stateの誤認防止だけを目的とし、新しい依存freezeを宣言しない。
