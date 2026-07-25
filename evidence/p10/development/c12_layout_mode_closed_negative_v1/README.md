# C12 layout-mode closed-negative v1

このdirectoryは、P3 provenanceに一致する二つのlegacy layout-mode harnessを
実行せず保持し、C12の同一surfaceをnegative-onlyで閉じたdevelopment証拠で
ある。task/game/level identity、固定座標、public replay bootstrapはA層証拠に
だけ残し、Runtime P入力には使用しない。

primary C12 harnessは5 target / 212 probe / 140 visible change /
104 layout-mode changeで、progress 0、GAME_OVER 0、progress/hazard/promotion
separator 0だった。auxiliary harnessも5 target / 176 probe /
86 visible changeで、progress 0、GAME_OVER 0、positive pre-action variable 0
だった。primaryのlegacy contract-spec mismatchとauxiliaryのpublic replay
bootstrapは明示的にquarantineした。

- HDS: `REJECT / CLOSED_NEGATIVE`
- tier: `LOCAL_PROBE`
- same surface retry: 不許可
- Runtime P compile / promotion: 不許可
- score progress claim: 不許可
- active P / 35 level境界: 不変
- next work block: `WB-C1_rendered_affordance_objectizer`

| artifact | SHA-256 |
|---|---|
| admission audit | `145f2df2429ce3d0b116d39d41a0c790e2ed3c3d5518b7bb90dd5746539071df` |
| primary frozen C12 harness | `3ca11339393f4c4410974e676cf163099a2da36030d869dd10c45d5c4364df40` |
| auxiliary frozen layout harness | `bb9ce326f52709ad9395c1a7db959c520f8b634750265f735db5edda827479fd` |

content digest:

`arc3_p10_c12_closed_negative_admission:dfd7b4f3fd4cdd507ba7c5b41aa33a7d8cebf44326a5df8f2363cedda68d6e81`
