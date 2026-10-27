# C2-049 rolling-summary turn-context candidate record

## Current state

- Prepared locally only; not pushed or run.
- The active C2-047 version 14 must reach terminal status and its output must confirm summary creation plus history replacement before this candidate is eligible to run.
- No official competition rerun, submission, or quota consumption.

## Evidence and change

The C2-047 embedded patch sets `_summary_turn_context()` from `ARC3_SUMMARY_TURN_CONTEXT`, default false. Its code comment says summary requests run before the current turn opener and a recent `level_completed` payload can be mistaken for the current level. With the flag on, `_summary_turn_context_lines()` is included in the summary request. C2-049 adds only `ARC3_SUMMARY_TURN_CONTEXT=True` to notebook cell 5; parsed notebook comparison confirms cell 5 is the only changed cell. Kernel metadata bytes remain identical.

Candidate notebook SHA-256: `ed85f5a045237bec275845b2fdcf6590c2cc8ccfa8ca933f48e6e9602766bdda`

Metadata SHA-256: `e31a7418a9430d0a343cac1dad9e408a3bafa64970d830d3f1be82742ed49372`

This is a source-path audit, not evidence of score improvement. Evaluation and adoption gates are in `運用/ARC3-RUN-003/C2-049_summary-turn-context-pilot.md`.
## Context payload inspection

The context builder includes executed-action count/names, interior-board change status, no-op/guard stops, level-completed/game-over/reset outcome, and the current step plus level. This confirms the flag supplies the exact transition facts the generic summary prompt otherwise may misread. The candidate remains unrun; this is implementation evidence only.
