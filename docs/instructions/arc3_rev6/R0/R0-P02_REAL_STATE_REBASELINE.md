# R0-P02 — 実状態再基準化

- Point ID: `R0-P02_REAL_STATE_REBASELINE`
- Depends on: R0-P01 PASS
- Next: `M0-P01_CAPABILITY_COVERAGE_MATRIX`

## 目的

文書上の完了状態ではなく、現行code／P／J／M／公式結果が実際に持つ能力を基準化する。

## 入力

- 現行mainのproduct runtime code
- active P／P-IR／initial-state bundle
- official submission ref 55206302とscore 0.06
- PH-D05 teacher corpus
- 公式サンプル25 game／183 level

## 必須作業

1. 公式入力から外部actionまでの実行経路を一つに特定する。
2. active P、P-IR、J config、M0、Runtime Mを列挙する。
3. teacher／replay／source由来のruntime依存を追跡する。
4. 公式sample上の実際のgame WIN／level completeを、空artifactや自己申告ではなく実行可能な証拠から確定する。
5. official score 0.06を外部実測として保持する。
6. 未成立能力を`representation / goal / mechanism / planning / binding / memory / resource`へ分類する。
7. shell、runner、packageを作らない。

## HDS焦点

```text
F: 現在実装と外部実測
Md: 実能力モデル／過大claimモデル／replay依存モデル
Cm: 証拠がある能力だけ採用
U: RealStateBaselineへ固定
```

## 出力

`analysis/product/rev6/R0_P02_REAL_STATE_BASELINE.json`

## Hard Exit

```text
one actual runtime path identified
actual active P/J/M identified
actual official score recorded
real sample completion count recorded or explicitly UNKNOWN
replay/source dependencies classified
unsupported completion claims = 0
```

## 禁止

- mock結果をactual completionへ加算
- 空run artifactを証拠化
- 既存shellの再命名
- product statusをCOMPLETEへ戻す

## Failure Routing

実結果を取得できない項目は`UNKNOWN`とし、推測で埋めない。Hard Exit後にM0-P01へ進む。
