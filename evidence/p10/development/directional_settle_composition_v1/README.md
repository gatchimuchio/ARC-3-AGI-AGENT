# Directional-settle composition v1

このdirectoryは、既存のmulti-actor、directional-force、obligation
capabilityへ、進捗直後の旧actionを最大8回だけ再観測するC5候補を合成した
`LOCAL_PROBE`証拠である。全artifactはdevelopment-onlyで、Runtime P入力には
使用しない。

同条件二重実行では、stable FT09はactive/candidateとも6/6を維持し、KA59は
双方6/7、220 actions、error 0だった。candidateはaction 193の進捗後、
action 194–201で旧directional actionを8回再送し、進捗0のままaction 202で
generic fallbackへ戻った。候補の発火とparameter消費は確認したがtarget deltaは
0なので、HDSは`REJECT / CLOSED_NEGATIVE`とした。

- all-sample regression: 不許可
- Runtime P promotion: 不許可
- score progress claim: 不許可
- active manifest: 不変
- candidate slot: 元のbytesへ復元
- 同一の旧action replay軸の再試行: 不許可
- 次に必要な変数: predecessor actionではなく、進捗後に見える新しいobligation
  stateのparseとcomposition

| artifact | SHA-256 |
|---|---|
| composition audit | `1c3a38457baa232d0b78625bd6ff6871e0593789b8d6664bcf574806afdb04e9` |
| candidate intervention audit | `addf0b1a782747930684b16bb2e50e432961c31c73fcb8b2a0024fb0e3db9593` |
| candidate target compact trace | `005d4d9e0376fc069f30f094f41812753e2c821c20369253317d5a3afbaecb64` |
| closed-negative failure audit | `6f1518ed26e67720c441415b86d4a1ac68fa2ebe33809e501c44cd229595728a` |
| archived candidate manifest | `75129d5bc41fd455f986309847b0b0fa4b4a54d2d40e33a1df2b24d3edd4715e` |
| archived candidate body | `6d56f9d9294a44720a61d711922317aeff50480581166378a61eb0f21b4cebe3` |

content digest:

- composition:
  `arc3_p10_directional_settle_composition_audit:d378a09b0dfb48c80d8fa46e08284fdea22da266568ecda2a2a0a5de5f16dfd7`
- intervention:
  `arc3_p10_directional_settle_candidate_intervention:d3d6b42db423eb00632acf7f40582e99555c686719839f7c04d8eaba81110a17`
- failure:
  `arc3_p10_directional_settle_failure_audit:61eac5c738790f378dfffb566c9f6fff1bb55a588749afc31df8a6137158ecab`
