# Historical Assets Index

このdirectoryは、ARC3開発中に成立した旧正本・旧authority・旧release・旧submissionを**削除せず、現在の権威面から分離して読むためのindex**である。

## Classification Rule

```text
CURRENT
= root AGENTS.md
+ control/CURRENT_SELECTOR.json
+ control/rev6/CURRENT_TASK.json
+ rev6 active Point instruction

HISTORICAL
= 上記CURRENTから選択されない旧文書・旧control・旧artifact・旧release
```

HISTORICALは「無価値」「削除対象」を意味しない。設計遷移、失敗、実装資産、再利用可能部品、反証の証拠として保持する。ただし、current completion／release／phase authorityへは昇格させない。

## Preserved Root Documents

`rev3_root/`には、rootでcurrentに見えていたrev3系文書の原内容をそのまま保存する。

- `rev3_root/AUTHORITY_ORDER.md`
- `rev3_root/DEPENDENCY_LOCK.md`
- `rev3_root/SCOPE_LOCK.md`

## Other Historical Surfaces

物理移動によるimport・build・Kaggle path破壊を避けるため、今回は以下を元位置に保存したまま論理的にhistorical分類する。

- rev2／rev3／rev4／rev5.1 strategy・roadmap・instructions
- P0〜P22、PH-D系control／evidence／artifact
- `release/ARC3CompletionAgent-v1.0/`
- `release/rev5_1/`
- `kaggle_notebooks/`のrev5.1 build／submission資産
- `ARC-AGI-3-Agents/`内の旧P番号実装・監査入口

実装本体を再配置する場合は、rev6 `R0-P02_REAL_STATE_REBASELINE`以降に実行経路・build・submissionへの影響を確認してから行う。
