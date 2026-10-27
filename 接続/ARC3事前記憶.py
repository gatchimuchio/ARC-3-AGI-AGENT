from __future__ import annotations

from typing import Any

from hds学習系統.型 import 外部入力


"""ARC3公開学習由来のID-free prior contextを、隔離したHDS境界へ記録する。"""

VERSION = "arc3-prior-context-v0.1"
BOUNDARY = "ARC3事前記憶"
SOURCE = {
    "source_kind": "ARC3 official public-sample-derived memory v0.4",
    "readme_sha256": "020018ae96f36bc7670c7215c469b83d2c8ebf06cf524831206d7a3bd38b29c8",
    "manifest_sha256": "d1b6e0cc3d14ce7c40c26567fefa226a2975c2e6d02725fb8bb404833963a1bd",
    "canonical_sha256": "b8cc8f90479bb08dbe119a62da3f608156f86be9cdb4084db5277bdbea7e6359",
    "distribution_scope": "private competition runtime only; do not publish this source during the competition",
}

# Only cross-game process principles are retained. Replay/known-answer reuse and
# retention of ID-linked raw records are intentionally omitted.
PRINCIPLES = (
    (
        "role_relation_first",
        "Model entities by their roles and relations before relying on absolute position or a distinctive color.",
    ),
    (
        "preserve_competing_hypotheses",
        "Keep materially equivalent explanations open until public evidence separates them; never choose by answer or identifier.",
    ),
    (
        "update_from_observed_deltas",
        "Record pre-action and post-action observations; visible change alone does not establish causality.",
    ),
    (
        "strip_identifiers_from_cross_episode_memory",
        "Cross-episode memory keeps conditions, roles, transitions, and failure boundaries while removing task, game, and level identifiers.",
    ),
    (
        "retain_unresolved_causality",
        "Keep unresolved mechanisms explicit and let the next public observation test them; known answers or source code do not prove mechanism closure.",
    ),
)


def 事前記憶をHDSへ供給する(hds: Any) -> dict[str, Any]:
    """Record ID-free principles as unverified context, isolated from game inference."""
    process = getattr(hds, "処理する", None)
    if not callable(process):
        raise TypeError("HDS prior context requires a process-capable learning system")

    for category, principle in PRINCIPLES:
        process(
            外部入力(
                {"記憶種別": "ID-free prior context", "原則分類": category, "原則": principle, "因果確認済": False},
                BOUNDARY,
                主体="ARC3 public-sample-derived prior context",
                対象=category,
                目的="Unverified design context only; not an answer map, action rule, or action authorization.",
                文脈={**SOURCE, "principle": principle, "causal_confirmed": False},
            )
        )

    return {
        "version": VERSION,
        "loaded_count": len(PRINCIPLES),
        "boundary": BOUNDARY,
        "action_authorization": False,
        # Test hypothesis: an observed delta is not causal evidence by itself.
        "visible_change_coefficient": 0.0,
    }
