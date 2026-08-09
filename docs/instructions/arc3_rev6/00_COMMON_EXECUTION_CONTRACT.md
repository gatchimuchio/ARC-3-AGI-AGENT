# rev6 全Point共通実行契約

## 1. 最終目的

`ARC3CompletionAgent`が同一artifact／同一ProductBundleで公式25 game／183 levelを自律完遂すること。

## 2. Current Point拘束

- `control/CURRENT_SELECTOR.json`の`active_instruction_path`だけを実行する。
- 他Pointを先行・同時完了しない。
- `auto_advance_allowed`は常にfalse。

## 3. Capability Closure Unit

```text
product gap
→ HDS F/Md/Cm/U
→ product capability change
→ official sample execution
→ result delta
→ regression
```

## 4. 実結果必須

Capability closure Pointは、mock／synthetic／teacher replayだけでPASS不可。公式サンプル環境のgame／level／Failure Signature差分を要求する。

## 5. 禁止

- 新しい空shell／agent subclass
- parallel runner
- analysis-only completion
- artifact existenceによる自動PASS
- game／level ID router
- exact frame hash lookup
- fixed trajectory playback
- J bypass

## 6. 能力資産状態

`LOCAL_M → PROBATION_DEV → ACTIVE_DEV → RELEASE_FROZEN`

## 7. Point Report

```yaml
PointReport:
  point_id:
  instruction_path:
  product_gap:
  HDS_finding:
  product_change:
  official_execution:
  games_before_after:
  levels_before_after:
  failure_signature_before_after:
  regression:
  hard_exit_results:
  status:
```

Hard Exit未達なら`REWORK_REQUIRED`とし、次Pointへ進まない。
