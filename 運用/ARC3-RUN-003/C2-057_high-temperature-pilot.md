# C2-057: high-temperature private pilot

## Hypothesis

C2-056 tested analyzer temperature 0.2 against the C2-046 slim control at 0.7. Its mean was 13.949735 vs 19.309156, paired delta -5.359420, with 1 improved / 1 unchanged / 1 regressed and 6 vs 7 completed levels. The mixed result does not establish a monotonic temperature effect. C2-057 tests one adjacent high-side setting, 0.9, to evaluate whether greater sampling diversity helps action selection. It is exploratory; no improvement is assumed.

## One-factor change and gate

Only cell 5 changes `LOCAL_ANALYZER_TEMPERATURE` from 0.7 to 0.9. All 25 cells remain; kernel metadata remains byte-identical, private, GPU-enabled, and Internet-disabled. Use the same three public starts, seed, and limits. Recompute with `EnvironmentScoreCalculator`; accept only if mean is strictly above 19.309155943771326 and paired mean delta is positive. A passing pilot still requires matched public-25 validation before promotion.

## State

Prepared and preflighted for one private run. No official submission or quota use. Candidate and preflight hashes are in `attempt-manifest.json`; detailed checks are in `運用/証拠/ARC26-UNIFIED/ARC3-C2-057-preflight-20261025.json`.

## Version 26 queued

Private kernel version 26 was pushed after preflight. The exact remote versioned pull matched all 25 candidate cell sources; only cell 5 differs from C2-046 slim. Status at first read: KernelWorkerStatus.QUEUED. No official competition submission or quota use. See the remote verification evidence and checkpoint.
## 2026-10-25 10:01 UTC — version 26 running

Kaggle reports exact private version 26 as KernelWorkerStatus.RUNNING. The run has no terminal output or score yet; no additional push or official submission was made. Next status check: 2026-10-25T10:16:10.418Z. Evidence: $rel (SHA $hash).

## Version 26 terminal result — rejected

The exact versioned output was recovered to `運用/証拠/ARC26-UNIFIED/ARC3-C2-057-v26-output` (31 files; 125,442,225 bytes; manifest SHA `fc934adb9400c21a1748dc254093b8358fb4479c0c0949957d8bf595e6de275d`). Recomputed scores matched the candidate's saved scores. The three start boards, event fields, level counts, and public baseline action arrays matched C2-046 slim.

| Metric | C2-057 v26 | C2-046 slim | Delta |
|---|---:|---:|---:|
| Mean score | 17.370128799908077 | 19.309155943771326 | -1.9390271438632496 |
| Improved / tied / regressed | 0 / 1 / 2 |  |  |

C2-057 completed 6 total levels versus 7 for the control, used 393 actions versus 389, and all three runs ended `gave_up`. **Reject** because mean was below 19.309155943771326 and paired delta was negative. No official submission or quota was used. Scorecard `運用/証拠/ARC26-UNIFIED/ARC3-C2-057-v26-terminal-scorecard.json` SHA `1ebdf1c18a3ce0307a0f54e94b56ee853e71efa4fba40baf021567c37b25a0c8`; scorer `運用/証拠/ARC26-UNIFIED/ARC3-C2-057-v26-scorecard.py` SHA `6849a98278a2301609e3e19c937a4489c49915efb17dad7d60d06a4772d24afe`.