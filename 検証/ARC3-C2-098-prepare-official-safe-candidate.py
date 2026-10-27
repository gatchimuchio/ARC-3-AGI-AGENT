from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PACKAGE = (
    ROOT
    / "出力/ARC3-RUN-003-local/C2-088/C2-088-B-v3-run-package"
)
EXPECTED_SOURCE_NOTEBOOK_SHA256 = (
    "8ca755c12e89ae117af160267d8471f8980574d19e687bdd50f146ef36b103bf"
)
EXPECTED_KERNEL_ID = "tecchannn/arc3-v6-online-official-c2-088"
GUARD = (
    'if TRUE_SUBMISSION:\n'
    '    raise RuntimeError("C2-078 is an offline pilot; competition rerun is not enabled.")\n'
)
REPLACEMENT = (
    "# C2-098: allow the official Competition Rerun path; cell 5 sets submission mode.\n"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare a separate official-safe copy of exact C2-088 v5 by removing "
            "its unconditional Competition Rerun rejection guard."
        )
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "出力/ARC3-RUN-003-local/C2-098/official-safe-v1",
    )
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite candidate directory: {output_dir}")

    source_notebook = SOURCE_PACKAGE / "submission.ipynb"
    source_metadata = SOURCE_PACKAGE / "kernel-metadata.json"
    source_bundle = SOURCE_PACKAGE / "visual-hds-source.zip"
    if sha256(source_notebook) != EXPECTED_SOURCE_NOTEBOOK_SHA256:
        raise ValueError("Source notebook differs from the exact preflighted C2-088 v5")

    notebook = json.loads(source_notebook.read_text(encoding="utf-8"))
    original = copy.deepcopy(notebook)
    if len(notebook.get("cells", [])) <= 6:
        raise ValueError("Expected C2-088 v5 cell 6 is missing")
    cell = notebook["cells"][6]
    source = cell.get("source")
    if not isinstance(source, list):
        raise ValueError("Expected notebook cell source as a list of lines")
    cell_text = "".join(source)
    if cell_text.count(GUARD) != 1:
        raise ValueError("Expected the exact fatal Competition Rerun guard once")
    if "Only off/shadow are validated; hints are not supported." not in cell_text:
        raise ValueError("Unexpected HDS mode contract in C2-088 v5")
    patched = cell_text.replace(GUARD, REPLACEMENT, 1)
    if "competition rerun is not enabled" in patched:
        raise ValueError("Competition Rerun rejection text remains in cell 6")
    compile(patched, "C2-098-submission-cell-6", "exec")
    cell["source"] = patched.splitlines(keepends=True)

    comparison = copy.deepcopy(notebook)
    comparison["cells"][6]["source"] = original["cells"][6]["source"]
    if comparison != original:
        raise ValueError("Candidate changed notebook content outside the one guard edit")

    metadata = json.loads(source_metadata.read_text(encoding="utf-8"))
    if metadata.get("id") != EXPECTED_KERNEL_ID or metadata.get("competition_sources") != [
        "arc-prize-2026-arc-agi-3"
    ]:
        raise ValueError("Kernel metadata no longer targets the expected private ARC3 kernel")

    output_dir.mkdir(parents=True, exist_ok=False)
    output_notebook = output_dir / "submission.ipynb"
    output_metadata = output_dir / "kernel-metadata.json"
    output_bundle = output_dir / "visual-hds-source.zip"
    output_notebook.write_text(
        json.dumps(notebook, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    shutil.copy2(source_metadata, output_metadata)
    shutil.copy2(source_bundle, output_bundle)

    reopened = json.loads(output_notebook.read_text(encoding="utf-8"))
    reopened_source = "".join(reopened["cells"][6]["source"])
    if "competition rerun is not enabled" in reopened_source:
        raise ValueError("Written candidate still contains the fatal guard")
    if reopened["cells"][5]["source"] != original["cells"][5]["source"]:
        raise ValueError("TRUE_SUBMISSION detection was altered")

    print(
        json.dumps(
            {
                "schema": "arc3-c2-098-official-safe-notebook-preflight.v1",
                "candidate_dir": str(output_dir),
                "source_notebook_sha256": sha256(source_notebook),
                "candidate_notebook_sha256": sha256(output_notebook),
                "source_metadata_sha256": sha256(source_metadata),
                "candidate_metadata_sha256": sha256(output_metadata),
                "source_bundle_sha256": sha256(source_bundle),
                "candidate_bundle_sha256": sha256(output_bundle),
                "kernel_id": metadata["id"],
                "removed_guard_count": 1,
                "changed_cell_index": 6,
                "only_guard_changed": True,
                "cell_6_compiles": True,
                "true_submission_detection_preserved": True,
                "hds_mode": "shadow",
                "official_submission_or_kernel_push": False,
                "gpu_quota_used": False,
                "score_effect": "NOT_MEASURED",
            },
            ensure_ascii=True,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
