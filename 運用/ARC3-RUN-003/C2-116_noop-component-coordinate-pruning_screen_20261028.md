# C2-116 — same-color component no-op pruning screen

Observed: `2026-10-28T00:32:01.471Z`.

## Candidate and comparison

The evaluation-only candidate uses the public board. When ACTION6 leaves the board unchanged, produces no visible cell changes, and does not advance a level, it marks the clicked cell's 4-neighbor same-color component as tried for that exact board. It does not use game IDs or hidden state. The control is the C2-111 retained online exploration policy. Both arms use seed 7, the same five public starts, and an 80-action budget per game.

| Metric | Control | Candidate | Delta |
|---|---:|---:|---:|
| Mean RHAE | 0.238095238 | 0.238095238 | 0 |
| Matched starts | 5 | 5 | 5/5 |
| Positive / negative / tied pairs | — | — | 0 / 0 / 5 |
| Levels / wins | — | — | 0 / 0 |
| Actions | 400 | 400 | 0 |
| No-ops | 9 | 9 | 0 |
| GAME_OVER | 6 | 6 | 0 |
| Illegal actions | — | 0 | — |
| Component no-op events / extra cells marked tried | — | 4 / 746 | — |

The predeclared `+0.01` mean-RHAE screen gate failed. The candidate changed the coordinate search bookkeeping but did not change score, progress, action count, or no-op count. **Reject after screen; do not expand to 15 pairs or promote.** The production agent, HDS, memory, and Notebook were not changed. No Kaggle kernel push or official submission occurred.

## Reproduction and evidence

Runner: `検証/ARC3C2-116_noop-component-coordinate-pruning-screen.py` (SHA-256 `4DE3E2123C8CE1BA5D9BDBC24823B64B352A857C33BC57184031130EB12BBB21`). It uses `検証/ARC3C2-109_ACTION6-family-HDS-paired-evaluation.py` (SHA-256 `13C18DDBA7C5777C3E6C5038CC2A0AD00F5B16498E9AE08A0ABFB3862AB76CD1`) and the frozen C2-111 control evidence.

Full paired result: `運用/証拠/ARC26-UNIFIED/ARC3-C2-116-noop-component-coordinate-pruning-result-20261028T003201Z.json` (SHA-256 `651676374B0817E6484F622F68E9337B6AFF847FD5E12CBA83B30B18756D37D1`). Screen evidence: `運用/証拠/ARC26-UNIFIED/ARC3-C2-116-noop-component-coordinate-pruning-screen-20261028T003201Z.json` (SHA-256 `5C1F1F80DE5B542FAD54680DAD9B12CBFF10CFE9E0AD741FACABE9F586DE5CA3`).

The v6 common and ARC3-specific three-point set, `AGENTS.md`, and `制御/現在状態.json` were rechecked before the experiment. Their hashes are in the screen evidence; protected files remain unchanged.