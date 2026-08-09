# M2-P01 — Clean Full Run A

- Point ID: `M2-P01_CLEAN_FULL_RUN_A`
- Depends on: M1-P07 PASS
- Next: failureあり→M2-P02／全数PASS→M2-P04
- Product capability change: 禁止

## 目的

一つのACTIVE_DEV ProductBundleをfresh stateから公式順序の全25 gameへ連続実行し、full-run固有failureを観測する。

## 実行契約

```text
fresh OS process or equivalent isolated process
fresh CognitiveSession
fresh Runtime M
one immutable ACTIVE_DEV ProductBundle
one product runtime path
official game order
25 official environments
```

## 必須作業

1. bundle digestを開始前後で確認する。
2. 全25 gameを中断せず順次実行する。
3. game WIN、levels、actions、stop reason、failure、memory transitionを記録する。
4. 人間による途中修正を入れない。
5. run evidenceを実データとして保存する。

## 出力

`analysis/product/rev6/m2/clean_run_A.json`

空ファイル、要約のみ、自己申告countは禁止。各game rowと実行trace参照を必須とする。

## Hard Exit

```text
official_games_attempted = 25
fresh_process_count = 1
fresh_session_count = 1
active_bundle_count = 1
bundle_mutation_count = 0
manual_intervention_count = 0
per_game_rows = 25
run_file_nonempty = true
```

## Routing

- failureあり → M2-P02
- 25/25 WINかつ183/183 → M2-P04

## 禁止

- teacher replay
- source-assisted step injection
- game間の手動patch
- rev5.1 run evidence流用
