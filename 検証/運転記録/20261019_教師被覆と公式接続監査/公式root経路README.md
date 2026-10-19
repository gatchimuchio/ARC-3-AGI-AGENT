# Supplemental official root-domain route check

Checked 2026-10-19, read-only public interface evidence. No package import, upgrade, game-source inspection or credential use.

The official benchmarking client presently names https://arcprize.org as its default root and constructs GET /api/games. This verifies the root-domain URL as an official client route rather than a guessed endpoint. `build_headers` uses an environment key or an empty value; this alone does not prove unauthenticated server access. Sources:
- https://github.com/arcprize/arc-agi-3-benchmarking/blob/main/.env.example (web result crawled yesterday)
- https://github.com/arcprize/arc-agi-3-benchmarking/blob/main/main.py (`build_root_url`, `build_headers`, `fetch_available_games`; web result crawled today)

The concurrently accessible official SDK interface `arc_agi/base.py` still defaults to https://three.arcprize.org and supports a configurable root. It appends /api/games and /api/games/{game_id}; its metadata/list methods guard on a nonempty key. Anonymous-key acquisition exists, but was not invoked. Public docs agree with the SDK default. This is observed client/default coexistence, not proof of a global migration or either server's availability.
- https://github.com/arcprize/ARC-AGI/blob/main/arc_agi/base.py (web result crawled last week)
- https://github.com/arcprize/docs/blob/main/toolkit/arc_agi.mdx (web result crawled three weeks ago)

At 2026-10-19T03:16:40.351476+00:00, clean-environment urllib GET https://arcprize.org/api/games, Accept application/json, no authentication, no proxies and no redirects failed with `URLError: <urlopen error [Errno -3] Temporary failure in name resolution>`. No HTTP status or body was obtained. AS limit was 512 MiB, timeout 20 seconds, maximum admitted body 1 MiB. `request_result.json` preserves the result. Web open of the same verified URL returned Internal Error, also without HTTP status. These are transport/tool failures, not 401/403 or proof that the official endpoint is unavailable everywhere. No current 25-game/183-level inventory was retrieved.

Prior three.arcprize.org attempts remain preserved in arc-official-public-fetch-20261019. No further network repetitions are scheduled absent a new permitted environment/route. Exact raw GitHub file bytes and commit SHA were not obtained; citations record the displayed main-branch interface, not a pinned SDK upgrade. Additional lookup failures: guessed repository arcprize/arc-agi-3 returned 404; guessed arcade.py page timed out; directory navigation identified base.py as the actual Arcade interface. Initial authority read used nonexistent root main paths; corrected reread used arc-preservation-recovery-20261019/main.
