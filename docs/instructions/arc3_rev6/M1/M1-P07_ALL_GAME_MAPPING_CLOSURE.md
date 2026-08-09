# M1-P07 — 全Game／Level Mapping閉包

- Point ID: `M1-P07_ALL_GAME_MAPPING_CLOSURE`
- Depends on: M1反復で全対象が閉じたこと
- Next: `M2-P01_CLEAN_FULL_RUN_A`

## 目的

全25 game／183 levelを少なくとも一度実製品で完遂し、全raw actionをMechanism Segmentと製品能力へ対応づける。

## 必須作業

1. 25 gameの個別WIN evidenceを列挙する。
2. 183 level complete evidenceを列挙する。
3. 全11,574 canonical actionをsegmentへ一意対応する。
4. 各segmentをACTIVE_DEV family、PROBATION residue、明示的Domain-Local Residueへ割当てる。
5. すべてのprimary analysisにproduct mappingを持たせる。
6. runtime execute eligibilityとanalysis-only residueを分離する。

## Hard Exit

```text
individual_official_game_WIN_count = 25
individual_official_level_complete_count = 183
mapped_raw_action_count = 11574
unmapped_raw_action_count = 0
overlapping_raw_action_count = 0
unused_primary_analysis_artifact_count = 0
one_ACTIVE_DEV_ProductBundle = true
manual_intervention_count = 0
fixed_playback_count = 0
```

過去rev5.1自己申告runは加算しない。

## 禁止

- teacher replayをindividual WIN evidence化
- empty artifact
- declarative residueを実行能力と偽装
- 25/183未達のままM2へ進む

## Failure Routing

未完遂game、unmapped segment、未接続analysisが一つでもあればM1-P02へ戻る。
