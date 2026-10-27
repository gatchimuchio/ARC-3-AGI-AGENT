# ARC3-RUN-003 C1-017：model-guided v5の公開25環境scorecard再採点

## 判定

同一公開25環境・同一開始状態における保存済みlocal v4 seed31とmodel-guided private v5を、公式 `EnvironmentScoreCalculator` でpaired再採点した。v5は平均scorecardを `0.227532 → 11.523217`、差分`+11.295685`点とし、25環境中22改善・2同点・1後退だった。保存private benchmarkのper-run `final_score` と再計算値も25/25一致し、baseline側の平均はC0 seed31集計と一致した。

これは公開環境での**ローカル公式scorecard計算**であり、Kaggle Competition再提出・公式採点ではない。完了levelは`3 → 47`（+44）だが、candidateのWINは0、25 runすべて`gave_up`、4 runは1200秒上限に達した。したがってmodel-guided v5を次の提出候補の技術監査対象として支持する一方、公式候補・公式改善とはまだ扱わない。

## Paired集計

| 指標 | previous：local v4 seed31 | current：model-guided private v5 | delta |
| --- | ---: | ---: | ---: |
| EnvironmentScoreCalculator平均 | 0.227532 | 11.523217 | +11.295685 |
| 完了level | 3 | 47 | +44 |
| action合計 | 2,000 | 1,906 | -94 |
| WIN | 0 | 0 | 0 |
| 環境別score | — | 22改善 / 2同点 / 1後退 | — |

25/25でpublic input metadataのhuman `baseline_actions` がcandidate記録と一致。開始board/state/levelは比較artifactで25/25一致を確認した。4 runがper-game 1200秒上限に達し、currentのfinal stateは全25 `gave_up`。total action差は記録値を併記したもので、成功や勝利を意味しない。

## 採点根拠・再現性

- 正本は`運用/ARC3文書正本.md`のv3.0。C2-027 private kernel version 5の保存出力とC2-025 local v4 seed31結果をread-onlyで使用。IDはメモリ内pairingにだけ用い、個別値を出力しない。
- previous結果SHA256 `5db40eb97823aaf5304c1c9ff40ec64b22618b0d98a5e09de1d61a109f355a31`、C0公開25結果SHA256 `ccbaf9e5011490618d2b0ff63e4e300e403644536fa3780061d8afbdfc6e23c5`。
- candidate benchmark SHA256 `7237a2d2150820ee2aadc8ba986dcb67a12e495bd934bd686583b1cd32ebdcd2`、paired comparison SHA256 `4bd0bf8b3f966f098d0a8ddca98038f1abdd8a5836af02718d528fb2282a730b`、出力manifest SHA256 `1d7b5e3edce18cfd166b2040235d03f0a8bc030711e1c763a72a9687799f7372`。
- evaluator SHA256 `3565ebe4fc61cc3cd666847064a64409b59a921ba47af393b286bce90be29bde`、targeted test SHA256 `7484e16992dafae6b1288974e5951bbc7602de976ed1fdc198b2595df76ef03`、anonymous output SHA256 `82fd23143e17a049a11f63601ad56135e2a6726611d775d78b4889cc5ee96ed3`、scorecard source SHA256 `1cc830e48008bec60b8a98ae14d3e9312e8408f102a9878bad42744aa9e489b7`。
- 公開入力50 files, content-set SHA256 `d40c652dfffda990a1a32c65da3d873a36bb9c4b6bd06598704596af3c2ead79`。targeted tests `3 passed`、Ruff check/format、py_compile PASS。
- 出力は匿名aggregateのみ。game/level ID、GUID、board、coordinate、action列、request transcriptを保存していない。公式Kaggle履歴・Notebook・kernel・agent/runtime・HDS・candidate・保護対象への書込み、提出、Competition Rerunなし。

## 次工程

candidate v5のsource/version同一性、competition-mode cell、internet-off依存、入力model weight、runtime budget、提出kernelへの適用経路をread-onlyで監査する。受入可能な同一artifactと競技条件が確認できた場合だけ、v3.0の提出適合確認と公式再採点へ進む。candidate v5を公式版として先取りしたり、古いkernel versionを現行版と取り違えたりしない。
