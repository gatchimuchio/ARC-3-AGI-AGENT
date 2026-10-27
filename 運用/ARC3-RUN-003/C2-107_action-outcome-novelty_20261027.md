# C2-107 — Action結果カテゴリの新規性bonus

観測時刻: 2026-10-27T20:44:54Z

## 目的と介入

C2-106では完全一致盤面の再訪が少なく、候補の効果は3/15対だけに限られた。C2-107では現在状態を同じ盤面に限定せず、各離散Actionが生んだ公開結果カテゴリをepisode内で記憶する。Actionごとに未観測の結果カテゴリが出たときだけ0.5の一度限りbonusを既存UCB報酬へ加える。カテゴリはafter-state、level進行有無、公開変化セル数bucket。Action 6は既存の座標探索に委ね、game ID・固定軌跡・hidden/evaluator情報は使わない。

## 条件と結果

固定shuffle seed `20261022`のdev 5公開環境、policy/environment seeds `7, 31, 73`、80 action上限で同条件paired評価を実施。

| 指標 | Baseline | Candidate | 差 |
|---|---:|---:|---:|
| mean RHAE | 0.240596656 | 0.240596656 | 0 |
| 改善/悪化/同点 | — | 0 / 0 / 15 | — |
| 完了level総数 | 3 | 3 | 0 |
| WIN | 0 | 0 | 0 |
| Action総数 | 832 | 835 | +3 |
| no-op総数 | 23 | 29 | +6 |

開始条件15/15一致。結果bonusは55回適用、action traceは9/15対で分岐したが全対score同点。scorecard契約違反0、illegal action 0、duplicate observation 0。平均RHAE差`+0.01`のdev gateを満たさないため候補は棄却し、holdout・runtime・HDS・Notebookへ進めない。

## 再現・証拠

```powershell
$env:UV_PROJECT_ENVIRONMENT=Join-Path $env:TEMP 'arc3-v6-locked-20261027'
python -m uv run --locked ruff check 検証/ARC3C2-107_action-outcome-novelty-paired-evaluation.py
python -m uv run --locked python 検証/ARC3C2-107_action-outcome-novelty-paired-evaluation.py --stage dev --output 運用/証拠/ARC26-UNIFIED/C2-107-action-outcome-novelty-dev.json
```

- Ruff: passed.
- Evaluator SHA-256: `17981d7c29b926a45507f3c128e138a4f690df608ca133a104ff9b3f84047076`
- Scorecard JSON SHA-256: `022149effeb555dfc8d52dbb711570eef8d2a092dfb4857706c58235dada039f`
- Local runner SHA-256: `ddcd523af222a95eb7a3ad1ae73351b011eccbcd25359eaa6b9c7a69792718e9`
- Agent policy SHA-256: `7879f85b5a3434dc2f5426c4837914c41054cbe56360ed4324167dab93de0575`
- RHAE evaluator SHA-256: `3e0edd03dfc81715191d6eb5a8a098eaddb1fd3eeb88205dd638d0b624b8c502`
- Environment manifest SHA-256: `a78d72e5ba7a2eb1166050719cdaa388ce415c251469a3641e695851839cb7f4`

## 正本・保護対象hash

作業開始時に共通3文書・ARC3専用3文書を再照合し、受領記録と一致。`AGENTS.md`・`制御/現在状態.json`は不変。

| 文書 | SHA-256 |
|---|---|
| 共通/Codex指示書.md | `e5f5c66f6391af6866211f9030b4cb08a0f0296063ab5bc53246529dc925a0c0` |
| 共通/工程表.md | `08c51299981c468712f66a560a50ab862843897d45ebbd965e0a032f35f71a25` |
| 共通/仕様書.md | `3a03343306aaf71cc9aa33100064f5476d8a7dad8b63567e5578c1a84d489141` |
| ARC3/Codex指示書.md | `47dd0ed72818e975af1fc9545808291effbf1b2ff7b524da9112f1ab8299a060` |
| ARC3/工程表.md | `34061bc53a228bcdc2b94cce7235ac96aa0e67f6bc74d2abb1757fe18af612b6` |
| ARC3/仕様書.md | `07ff22715feba930763fc01d10c1989e827aa6206cd45974d1fefed7d2060b67` |
| AGENTS.md | `dff057d8f6ac88c688ec1d950640dc88b706d5ed9184119deda226d0109a8d42` |
| 制御/現在状態.json | `0e4b29319d727896e244fe32f9726f0933f63fe007f59480272e76d46508c93c` |

## 公式履歴

Read-only Kaggle CLI履歴の20:38Z観測ではsubmission `57688735`が`COMPLETE`, public `28.07`, private未提供で、最新行に変化なし。比較元`57577905` public `23.86`から`+4.21`。提出枠の最終観測19:18:07Zは1件使用・残り0。C2-107はローカル評価のみで公式quota使用なし。
