# Historical Assets Index

このdirectoryは、ARC3開発中に成立した旧正本・旧authority・旧release・旧submissionを**削除せず、現在の権威面から分離して読むためのindex**である。

## Classification Rule

```text
CURRENT
= control/CURRENT_SELECTOR.json が選択する現行文書／state

STABLE OPERATING SURFACE
= root AGENTS.md
+ root AUTHORITY_ORDER.md
+ docs/operations/

HISTORICAL
= Selectorから選択されない旧文書・旧control・旧artifact・旧release
```

HISTORICALは「無価値」「削除対象」を意味しない。
設計遷移、失敗、実装資産、再利用可能部品、反証の証拠として保持する。ただしcurrent completion／release／phase authorityへは自動昇格しない。

## Preserved Root Documents

`rev3_root/`には、過去にrootでcurrentに見えていたrev3系文書の原内容を保存する。

- `rev3_root/AUTHORITY_ORDER.md`
- `rev3_root/DEPENDENCY_LOCK.md`
- `rev3_root/SCOPE_LOCK.md`

旧Dependency／Scope Lockはhistorical sourceとしてここに残し、現在のroot operating surfaceからは除外する。

## Preserved Runtime Documentation

`rev4_runtime/ARC-AGI-3-Agents_README.md`には、旧runtime READMEの原内容を保存する。
現在のimplementation READMEはcurrent selectorではなく、実装subtreeの入口としてのみ使用する。

## Other Historical Surfaces

物理移動によるimport・build・Kaggle path破壊を避けるため、以下は元位置に保存したまま論理的にhistoricalとなる場合がある。

- Selectorから選択されない旧strategy・roadmap・instructions
- 旧P番号／PH-D系control・evidence・artifact
- 旧release directory
- 旧Kaggle build／submission資産
- implementation subtree内の旧実験・監査入口

現行かどうかはdirectory名ではなくSelectorとcurrent evidenceで判断する。

## Preservation Rule

- historical evidenceを現在の説明へ合わせて書き換えない。
- 誤claimを訂正する場合は、旧recordを消さず新しいinvalidation／correction evidenceを追加する。
- cleanupだけを理由にpath-sensitive assetを移動しない。
- 過去資産を再利用する場合、現在のauthority・interface・evidence条件へ再接続してから採用する。
