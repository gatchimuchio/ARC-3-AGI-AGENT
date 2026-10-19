# Official reconnection feasibility audit — 2026-10-19

## Result

A practical new official connection is available in existing own-source/public contracts; fresh043 is not required. Installed distribution metadata reports arc-agi 0.9.9 and arcengine 0.9.3, the same versions used by the preserved official initial-observation contract. The Python 3.12.14 venv interpreter target exists and metadata for 31 installed distributions was read. This is metadata availability, not successful import or current binary/body-hash verification.

The immediate blockers are absent local game payloads, unverified current server inventory/access, and an unadmitted current SDK execution/resource boundary. A small public metadata + opaque download unit can address the first two before any SDK import or environment initialization. No credential creation/read is needed merely to try unauthenticated official GETs; whether they succeed is currently unknown.

No HDS/SDK import, environment creation/reset, action, network request, credential read, opaque SDK/game source-body read, evaluator inspection or Git write occurred in this audit. Owner originals, AGENTS, hierarchy and current state were reread. Work used a 512 MiB AS ceiling and stayed below 96 MiB disk. This is read-only feasibility work, not an implementation or fresh performance result.

## Exact existing public transport and source

Official base URL is documented in installed `arc_agi-0.9.9.dist-info/METADATA` and in the verified owned downloader: https://three.arcprize.org.

Existing official routes, copied from owned source rather than invented:

- GET `/api/games`: public environment inventory
- GET `/api/games/{versioned_game_id}`: public metadata, including baseline_actions
- GET `/api/games/{versioned_game_id}/source`: official downloadable execution payload
- GET `/api/games/anonkey`: historical anonymous-key acquisition; **do not call in the next unauthenticated fetch unit without resolving credential-creation authorization**

Exact owned downloader:
`evidence/arc-official-bundles-20261013/download_opaque.py`
7724 bytes, SHA-256 `10f678a54bbf1cdbce6737ff982b98d8a18a9119fa4b88b9d8878e4d0e8e3cfd`.
Its original member/hash is in `reports/download_source_pin.json`. Source GET passes `auth=True`, adding `X-Api-Key`; historical inventory/detail requests also used this header. The key was obtained in memory from anonkey and not persisted. Thus historical success is authenticated evidence. It does **not** establish that no-key GET fails or that the endpoints are reachable today. Do not run this historical script wholesale: it acquires a key and embeds old paths/budgets.

The SDK's installed README documents `Arcade(arc_api_key='', operation_mode=OperationMode.OFFLINE, environments_dir=...)`, and that an empty key outside OFFLINE automatically fetches an anonymous key. Therefore default/NORMAL/ONLINE construction is not an acceptable credential-free availability probe. It can also create a scorecard as a make side effect. Use direct bounded public GETs for metadata first; later choose explicit offline execution with clean environment and local opaque assets.

## Original archive is metadata-only for game bodies

The available sanitized archive is exact to its admission receipt: 1302802 bytes, SHA-256 `ab409c1855768cbf40634ad98236c0782a825ce7a9676ec98ef6c8b3d8212caa`.

Its original checkpoint README and manifest explicitly excluded all 25 game `.py` bodies before sanitization. `evidence/original_archive_excluded_game_sources.json` records the source URL, version, bytes and SHA for every game. The original Library checkpoint would therefore not restore those bodies either. The sanitized derivative additionally omitted 54 opaque stdout/stderr members (2889 bytes), a separate fact. The preliminary message attributing missing game bodies to sanitization was corrected after inspecting these exact records.

The archive contains 25 local game metadata.json files but no game payloads. No environment_files directory was found in the current workspace/shared search. The source URLs remain a legitimate official restoration route. Downloaded game bodies may be preserved/hash-checked/used solely as opaque execution assets in a separately admitted run; do not print, decode for inspection, parse AST or inspect evaluator logic. Publication exclusion is not itself a prohibition on official execution.

## Full inventory and freshness

`reports/last_verified_inventory_25_183.json` lists **all 25 versioned identifiers, individual level counts, full baseline_actions, source URL, source length/hash and payload availability**. Totals: 183 levels, 3969790 source bytes. This is the exact last verified public inventory, cutoff 2026-10-13T14:31:01Z; it was not refreshed by this no-network audit. A current claim of 25/183 requires a new public inventory/detail read. Do not force a changed current list to equal historical counts.

All 25 old baseline vectors matched the preserved prior index. That index uses base identifiers, so its version equality remains unknown despite equal baseline vectors. Historical initial observation evidence covers 25 make calls, 25 unique GUIDs and 27 frames, with levels_completed=0 and win_levels summing to183. It does not cover fresh entry to every183 level or successful gameplay.

Goal6's six public teachers are specifically from `cd82-fb555c5d`, which matches the last verified cd82 public version. It has six public levels, baseline_actions `[55,8,41,21,23,23]`. Exact official payload:

- URL: https://three.arcprize.org/api/games/cd82-fb555c5d/source
- Length:34381 bytes
- SHA-256:`dafeabff60a3a99b5c93629f8da0d8f555b873ef16a522247d6197b1b3addbcb`

This makes cd82 a justified bounded reproducibility target, not a game-ID solution route. Its ID can select an evaluation environment and provenance record; the runtime policy must only receive observed predicates. It is not evidence of cross-game transfer. If today's version differs, retain both and treat applicability as unverified.

## Existing fresh adapter and complete public contract

Own source: `evidence/arc-official-fresh-all25-20261013/prep/fresh_all25_v1.py`, SHA-256 `52904ce9357a933c2f53daf0cd23b5672dfdb30aef50844f89daa8b56a824516`.

The verified historical call shape is:

1. Explicit `Arcade(arc_api_key='', operation_mode=OperationMode.OFFLINE, environments_dir=..., recordings_dir=..., logger=...)`.
2. `arcade.make(versioned_game_id, seed=0, save_recording=False, include_frame_data=True, render_mode=None, renderer=None)`.
3. Read `env.observation_space`, requiring nonempty `arcengine.FrameDataRaw`.
4. Preserve `model_dump(mode='python', round_trip=True, exclude_none=False)` with types/order, JSON form and every frame's dtype/shape/strides/C-order bytes/hash. Do not retain only the final image.

The public metadata fields pinned in that version are `game_id, state, levels_completed, win_levels, action_input, guid, full_reset, available_actions`. Frame arrays are retained separately. The saved actual initial frames were int8 64×64. Supported state names in the existing adapter are NOT_PLAYED, NOT_FINISHED, WIN and GAME_OVER. Current public schemas must be checked before using historical assumptions.

Existing pure `../arc-semantic-rehost-20261019/origins/ARC3境界.py` provides `観測する`, `HDS観測入力` and `作用を排出する`. It validates 0..15 rectangular frames <=64×64, public legal actions, full-reset/status/run identity and monotonic observation sequence; it hashes all frames plus metadata and sequence. Action numbers are0..7; RESET=0, ACTION6 requires integer x/y in0..63, other actions take empty data. Public SDK `env.step(action, data=None, reasoning=None)` returns FrameDataRaw or None. The adapter passes fresh request-local dictionaries rather than mutating shared GameAction enums.

The adapter's `HDS確定作用` is only a transport form: a caller-supplied 確定 string is not proof of native acceptance. The owner must bind exact persisted native output/support/applicability/effect/preservation and current observation to an action. No such permission was constructed here.

Old public teacher recordings use `score`/`win_score`; the current pinned SDK raw model uses `levels_completed`/`win_levels`. The old endpoint-progress label must not silently be redefined as level progress or generic reward. Verify this public-version mapping before new comparisons/teachers. None/unchanged frames cannot establish no effect; preserve availability/status/reset/level changes and unknown hidden delta.

## Runtime projection for the newly learned goal6 relation

Existing own-source already defines the projection, so no new mechanism is needed:

- `../arc-teacher-contrasts-20261019/pinned/arc-goal-teacher-recovered-20261013/source/goal6_producer_v1.py`: `before_hypothesis` and whole-phase observation handling.
- Exact dependencies recovered as own-source evidence only: `evidence/goal6_知覚.py` SHA `24cf101fe67f8dd15c928751c8b63e8e79d33dadecd39655bf7745ec1154c950`, `evidence/goal6_関係.py` SHA `29860d6afbd34cef8a835fbc5b7fab815146e8f717f104a4e2b3983fa72d3349`. They are available in `goal6-checkpoint.tar.gz`, not missing historical bytes. Do not import their old top-level path/native plumbing; a named explicit-dependency pure rehost is the next small coding unit if needed.

The perception prior requires a64×64 frame, unique background, specific color4 reference frame/color swatches, a unique10×10 reference square, a unique unobscured10×10 target, red/color2 tool outline and an unambiguous tool color/nonzero relative direction. `classify` maps5 to wide painting as fixed prior; this action meaning is not newly learned by the goal6 truth table.

The fixed wide mask computes `depth=dx*(2*x-n+1)+dy*(2*y-n+1)` and proposes membership when depth>=0. `before_hypothesis` visits **all100 cells**: predicted color is tool color inside this fixed mask, otherwise current color; compare each with public reference. All currently deficient cells must be predicted repaired, and all currently satisfied cells predicted preserved. Unknown geometry/color produces undefined conditions/HOLD. Empty universal groups evaluateTrue; preserve both group counts so this is not mistaken for actual progress.

For a fully defined current before-hypothesis, encode the exact existing learned input, not a new two-Boolean schema:
`内容={'作用前の修復保全条件組':'[true,false]'}` (or the corresponding exact lower-case compact Boolean pair string), boundary `公開100対象・広域塗布・固定幾何上書き仮説の修復保全条件組と公開進捗`. Query actual frozen HDS `照会する(外部入力(...))`, inspect result leaf `公開進捗が増加`. Source/game/level/path/hash/replay IDs stay outside this input.

The parent reports the new descendant learning run closed; its outcome audit is separate and was not revalidated by this task. This projection does not promote its endpoint relation into action permission. Historical six cases have35 interpretable phases and77 unknown interpretations, and both positive endpoints changed final reference binding. Full continuous preservation, actual mask correctness, necessity, cross-version applicability, safe navigation/color changes and generic action safety remain unproved. A new initial observation may not satisfy this narrow grammar; retain that HOLD and all candidates, without replaying teacher action sequences to force an applicable state.

## Practical next units and stopping gates

1. **Public inventory/opaque restoration, no SDK:** direct unauthenticated GET of official list/detail, strict HTTPS/host/no redirects, bounded response and time. Refresh all returned inventory rows and retain old/new differences; don't silently require25. Try exact official versioned source download as opaque bytes. If401/403/auth challenge occurs, stop and report the exact endpoint; do not fetch anonkey, read stored credentials or switch automatically to SDK mode. If bytes match the saved length/hash, restore the exact asset; if they differ, preserve the response separately and treat it as new unadmitted evidence. Reuse explicit local metadata layout and never inspect game code. The old downloader provides boundary patterns but must not be launched unchanged.
2. **Pinned fresh initialization-only:** after current source/metadata and execution approval, one isolated cd82 instance, explicit OFFLINE/no network/no credentials/clean cwd+HOME, complete public packet preservation, no ordinary action or extra reset. Existing historical initialization used1GiB AS and120+120seconds; this audit's512MiB does not certify SDK execution under512MiB. Rebudget/import-profile with a preallocated failure reserve and genuine process isolation before launch. Historical socket-probe/cache failures must remain visible; Python audit hooks are not an OS sandbox proof.
3. **Fresh observation → existing goal6 predicates → native read-only Query:** independently pin the pure projection and complete100-target evidence, compare historical fixtures exactly, then query the newly audited descendant on the actual fresh observation. Preserve all responses/HOLD and paired-counter-only state change. This is fresh applicability/query evidence, not transfer success or action safety. No source IDs in decision features.
4. **One-action gate, only once justified:** independently verify every role/action mapping, present legal action, mask applicability, goal/repair/preservation evidence, exact native state/support/hold/conflict outputs, current full observation identity and durable before evidence. Treat unsupported/ambiguous claims as HOLD. Allocate all-after-frames/failure/hidden-unknown capture before emitting through the existing boundary. Do not infer permission from the endpoint-progress prediction alone. All candidates and unsupported families remain retained, with no pruning/top-k/beam. Reobserve and record public delta/failure even if pixels are unchanged; subsequent steps require new current evidence.
5. Fresh all25 initialization and eligible cross-game/level checks can be expanded only with complete current inventory, per-instance ownership and full resource accounting. Historical25-initial/183-metadata, fixture counts and newly taught experiences remain distinct from solved levels. Do not invent a planner or replay route merely to increase a success count.

## Evidence index

- `reports/read_inventory.json`: archive member hashes, installed dependency metadata and authority reread hashes.
- `reports/last_verified_inventory_25_183.json`: exact full historical inventory/source pins, freshness explicitly marked.
- `reports/sdk_metadata_only_status.json`: interpreter existence and historical SDK paths/stat sizes; no body/import claim.
- `reports/download_source_pin.json`: exact owned downloader origin.
- `evidence/`: only safe own-source, package public documentation and manifests/metadata; no game bodies or credentials.
- `MANIFEST.json`: all newly produced artifact hashes. These findings do not modify core, current state, old source or existing evidence.
