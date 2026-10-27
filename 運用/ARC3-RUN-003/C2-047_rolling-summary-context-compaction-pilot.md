# C2-047: rolling-summary context compaction pilot

## 仮説

C2-046 slim は off より level 完了が 6/21 から 7/21 へ増えたが、slim は3走中2走が1,200秒上限に達し、request 249件・prompt tokens 17,277,615となった。request本文の文字数（画像ブロックを除く）は、初回18,847、中央値38,197、最終56,395、最大59,854文字まで増えた。入力履歴の反復が実行時間を圧迫している可能性がある。

既存 rolling-summary 機能を32,768新規context tokensごとに呼び出し、有効な要約ができた場合に限り、それまでの会話履歴を要約で置き換える。これにより進行を維持しながら入力tokensとタイムアウトを減らせるかを測る。能力向上は仮定しない。

## 比較条件

- Historical control: C2-046 slim version 12（同一seed・3件の公開offline game）
- Treatment: C2-046 slim sourceへ `ARC3_SUMMARY_INTERVAL_TOKENS=32768` と `ARC3_SUMMARY_REPLACES_HISTORY=True` のみ追加
- `ARC3_SUMMARY_ENABLE_THINKING` は既定値（false）を維持。memory、loader、model、server、game limit、seed、action/time budgetは変更しない
- Kaggle kernelはprivate/GPU有効/Internet無効。公式competition rerun・submission・quota使用はしない

## 観測項目

同一初期公開状態、summary生成回数と履歴置換のログ、summary失敗・切断、level完了/WIN、action/no-op/illegal action、per-game timeout、runtime、request count、prompt/completion tokens、request本文文字数の中央値/p90/最大値を集計する。識別子、盤面、action列は記録・出力しない。

## 判定

- 同じ3初期状態を確認し、要約生成と履歴置換をログで確認する
- 進行がC2-046 slimの7/21を下回らず、timeoutsが2/3を上回らず、prompt tokensまたはruntimeが15%以上減った場合のみ「次の拡大検証候補」とする
- それ以外はこの圧縮設定を棄却または再設計する。3件のprivate評価だけで公式候補へ昇格しない

## 追加監査条件

- Summary replace後に `World model` / `Plan` section markerが後続turnへ再注入されるか、level-change直後のsummary文脈が stale になっていないか、summary出力長と履歴置換後のrequest本文長を集計する。summary instructionはlengthを制限しないため、単に有効化しただけでは圧縮を仮定しない。
- `ARC3_SUMMARY_TURN_CONTEXT` は今回既定値falseのまま。置換直後にlevel/stepを誤認する兆候、またはmemory markerの再注入欠落があれば、この設定は不採用とし、次の実験ではturn-contextを独立した追加条件として評価する。

## Scorecard primary outcome

C2-047の主判定は公式 `EnvironmentScoreCalculator` による公開環境scorecardとする。C2-046保存benchmarkの`final_score`を同calculatorで再計算した結果は6/6走一致。pairedのsmall-sample基準はoff平均12.735567、slim平均19.309156、slim差+6.573589（2改善・1後退）。C2-047はC2-046 slimと同じ3開始状態でpaired比較し、score deltaを最優先する。平均scoreが19.309156を超えず、かつpaired mean deltaが正でなければ、score改善候補として扱わない。効率だけ改善した場合は、score改善と区別して追加評価の判断材料に留める。これは公開offline scorecardでありKaggle公式提出scoreではない。

## Historical v5 subset reference (exploratory)

The three C2-046 game keys also occur in the saved 25-environment v5 benchmark. On this common-key subset, repository scorecard means are v5 4.761905, off 12.735567, slim 19.309156; slim exceeds v5 on all three paired keys. The v5 comparison artifact confirms v5 versus local-v4 board/state/level identity for those three; C2-046 separately confirms off versus slim start identity. Cross-pipeline identity is not directly hash-joined, so treat this as directional context only; C2-047's primary comparison remains the direct C2-046 slim pairing.

## Memory lifecycle scope

- C2-047 inherits `ARC3_WM_WIPE_ON_LEVEL=1` from C2-046. Its score effect concerns history compaction under the same within-level memory lifecycle; it does not evaluate cross-level retention.

## Runtime accounting

In these benchmark files, `game_runs[].final_wallclock_seconds` is cumulative from the shared benchmark start, not an individual game duration: all three `started_at` values match the benchmark start and the final cumulative value matches total benchmark duration. Compute each game's elapsed seconds as the difference from the preceding run's cumulative value (starting from zero), then verify the sum against `end_time - start_time`. C2-047 uses this delta method for timeout/runtime gates.

## Official-score objective

Kaggle history read on 2026-10-24 confirms submission 57577905 COMPLETE at publicScore 23.86; privateScore was not provided. This is the official baseline to beat: only a later scored Kaggle publicScore greater than 23.86 will establish official improvement. C2-047/048/049 runs on 3 public games (and any local public-25 validation) are candidate filters and are not numerically compared with the hidden competition aggregate. The official RHAE metric weights per-level squared human/action efficiency, caps each level at 1.15, weights levels by index, caps the environment by completed-level weight, and averages across games. Final selection must improve both progression depth and action efficiency before using an official submission.

## Official-run eligibility

Before any scored rerun, reread current submission limits and confirm quota is available. The official GPU Notebook must keep Internet disabled and complete within Kaggle's 9-hour runtime requirement. The last recorded quota observation was 0 remaining at 2026-10-24 10:48 UTC; this is historical, not a current allowance.
