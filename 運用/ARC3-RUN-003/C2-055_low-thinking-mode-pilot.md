# C2-055: explicit vLLM thinking-toggle private pilot

## Evidence and hypothesis

C2-046 slim is the current matched three-game local reference (mean 19.309155943771326). Its `requests.jsonl` has 247 model responses: 439,748 completion tokens, including 362,725 reasoning tokens (82.5%); median response 1,240 completion tokens and 950 reasoning tokens. The saved notebook sets `LOCAL_ANALYZER_PROVIDER='vllm'`. Across 496 request/response log entries, `chat_template_kwargs` never contains `enable_thinking`, while the SGLang `serve.log` reports `ReasoningToggleConfig(toggle_param='enable_thinking', default_enabled=True)`. Code-path review shows the environment-only setting reaches a provider argument that does not override the vLLM chat-template default. Therefore the initial environment-only C2-055 draft was ineffective and was superseded before any push.

The corrected hypothesis is that explicitly sending `enable_thinking=false` to the Qwen chat template may reduce reasoning generation and latency, leaving more of the fixed game-time budget for environment actions. It may also reduce decision quality; only the paired scorecard decides.

## One-factor change

Start from C2-046 slim. In cell 3, the shared request helper now includes `enable_thinking=False` in `chat_template_kwargs`. That helper is used both to build each request and to record the request kwargs, so the actual toggle can be verified from the candidate trace. All other cells and kernel metadata match C2-046; cell 5 retains the control's `LOCAL_ANALYZER_ENABLE_THINKING='true'` value so this treatment depends only on the explicit vLLM template kwarg.

## Acceptance and sequencing

Use the same three public starts and official local `EnvironmentScoreCalculator`. Accept as a pilot candidate only if mean is strictly above 19.309155943771326 and paired mean delta is positive. Also verify the captured `chat_template_kwargs.enable_thinking` is false and compare level progress, wins, actions, runtime, total/reasoning tokens, and terminal states. If it passes, evaluate matched public-25 before promotion and continue optimizing after any local threshold. This candidate is prepared only: do not push until exact C2-054 version 23 is terminal and rescored.

## Pre-run review

Notebook schema: nbformat 4.4, 25 cells. Only source cell 3 differs from C2-046 slim; all embedded unified-patch hunk counts validate (150). Kernel metadata bytes are unchanged: private, GPU-enabled, Internet-disabled. Notebook SHA-256: `c88af3f37aa9e6ff13a972f9fc07fbff1ae5042fa1d7be694d991305a6168777`. Metadata SHA-256: `e31a7418a9430d0a343cac1dad9e408a3bafa64970d830d3f1be82742ed49372`.

Baseline request-log SHA-256: `041c2aeee7dc283fd8324eff6932cea0938c63917ffa6173e706933c8c2c026f`. Reasoning-token aggregate and the superseded-candidate correction are recorded in `運用/証拠/ARC26-UNIFIED/ARC3-C2-055-template-off-correction-20261025T0438Z.json`.


## Control score revalidation — 2026-10-25 04:37 UTC

Recomputed all three C2-046 slim game scores with the active local EnvironmentScoreCalculator; mean remains 19.309155943771326 and each game matches the prior terminal scorecard. Evidence: 運用/証拠/ARC26-UNIFIED/ARC3-C2-055-baseline-control-recalc-20261025T043702Z.json.


## Sequencing clearance — 2026-10-25 05:38 UTC

C2-054 version 23 is terminal `COMPLETE` and has been rescored: mean 6.878307 versus C2-046 19.309156, paired mean delta −12.430849; reject C2-054 for score improvement. This completes the required predecessor review. The corrected C2-055 candidate remains one-factor (cell 3 only), with notebook SHA-256 `c88af3f37aa9e6ff13a972f9fc07fbff1ae5042fa1d7be694d991305a6168777`, identical private/GPU/no-Internet metadata, and `enable_thinking=false` in the shared request/log helper. It is now ready for one private offline pilot push. No official submission or quota use. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-054-v23-terminal-scorecard-20261025T053740Z.json`.


## Run update — 2026-10-25 05:44 UTC

After C2-054 version 23 was rescored and rejected, one private offline C2-055 pilot was pushed as exact kernel version 24. Exact status at 05:44:16 UTC was `KernelWorkerStatus.QUEUED`. Pulled version 24 and verified all 25 cell types/sources match the candidate; explicit `enable_thinking=false` remains in cell 3. Local candidate notebook SHA-256 `c88af3f37aa9e6ff13a972f9fc07fbff1ae5042fa1d7be694d991305a6168777`; metadata SHA-256 `e31a7418a9430d0a343cac1dad9e408a3bafa64970d830d3f1be82742ed49372`; remote notebook SHA-256 `a101e824985ad30a19c610569faacf24b0b5b1d46b0acf71c0223a641adea5fc`. No official submission or competition quota was used. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-055-v24-start-20261025T054416Z.json`, `運用/証拠/ARC26-UNIFIED/ARC3-C2-055-v24-remote-source-verification-20261025T054416Z.json`.


## Baseline output-cap review — 2026-10-25 05:49 UTC

C2-046 slim request-log audit: 247 model responses, 246 `tool_calls` and 1 `length`; 439,748 completion tokens, including 362,725 reasoning tokens (82.5%). 20/247 responses exceed 4,096 completion tokens and 2/247 exceed 8,192; one reaches the configured 12,288-token maximum. A lower output cap would constrain observed responses, so C2-055 keeps this limit fixed and isolates only explicit `enable_thinking=false`. Token reduction alone is not a score-improvement result. Source SHA-256: `041c2aeee7dc283fd8324eff6932cea0938c63917ffa6173e706933c8c2c026f`. Evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-055-baseline-output-cap-audit-20261025T054916Z.json`.
