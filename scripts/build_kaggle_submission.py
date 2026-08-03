"""Build the deterministic M4-P05 ARC3CompletionAgent Kaggle Notebook."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from textwrap import dedent
from typing import Final, Sequence

ROOT: Final = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR: Final = ROOT / "kaggle_notebooks"
COMPETITION_SLUG: Final = "arc-prize-2026-arc-agi-3"
DEFAULT_USERNAME: Final = "tecchannn"
DEFAULT_NOTEBOOK_SLUG: Final = "arc3completionagent-rev5-1-frozen-release"
WHEELHOUSE_DATASET_ID: Final = "tecchannn/arc3-completion-release-rev5-1"
WHEELHOUSE_DATASET_VERSION: Final = 1
WHEELHOUSE_DATASET_SOURCE: Final = (
    WHEELHOUSE_DATASET_ID + f"/{WHEELHOUSE_DATASET_VERSION}"
)
WHEELHOUSE_DATASET_SLUG: Final = "arc3-completion-release-rev5-1"
WHEELHOUSE_INPUT_ROOT: Final = "/kaggle/input"
WHEELHOUSE_MOUNT: Final = "/kaggle/input/" + WHEELHOUSE_DATASET_SLUG
WHEELHOUSE_MANIFEST_FILENAME: Final = "ARC3_M4_P05_WHEELHOUSE_MANIFEST.json"
WHEELHOUSE_MANIFEST_PATH: Final = ROOT / "analysis/product/rev5_1/" / (
    "m4_p05_kaggle_wheelhouse_manifest.json"
)
M4_P02_REPORT_PATH: Final = ROOT / "analysis/product/rev5_1/" / (
    "m4_p02_freeze_manifest.json"
)
M4_P04_REPORT_PATH: Final = ROOT / "analysis/product/rev5_1/" / (
    "m4_p04_clean_full_sample_closure.json"
)
RELEASE_WHEEL_PATH: Final = ROOT / "release/rev5_1/" / (
    "arc3_completion_agent_release-0.1.0-py3-none-any.whl"
)
RELEASE_WHEEL_SHA256: Final = (
    "b930ea1b339d4cb153f6ae153b3cec1e57ea1661dc40c7616a3ad6c6bc5790e4"
)
RELEASE_DESCRIPTOR_SHA256: Final = (
    "c86470412a3479115784c8620dcdfb6e68724dc1805c65d9a458c2bc23284d99"
)
RELEASE_PACKAGE_SHA256: Final = (
    "99dd28966a0c20eaf2d93c3c47746d81d0ff2de666290f33b13526e8e878c923"
)
RELEASE_RUNTIME_IDENTITY: Final = (
    "runtime-identity:47094e2ddb524bb1dba76078d51e10a20b090148bcd5b9a7c9cc4a20a416faff"
)
RELEASE_BUNDLE_ID: Final = "ARC3ProductBundle-release-v1"
RELEASE_BUNDLE_LOGICAL_DIGEST: Final = (
    "release-manifest:0b16e49719e326a1f51d81e5f107508025f1eeabe6735b205a11ebc233cb6489"
)
RELEASE_INITIAL_STATE_DIGEST: Final = (
    "initial-state-logical:a3fdd6b188538eda5b6837c1bddf5c60f46dc7c09ba03b47bc170d10e85f45bb"
)
RELEASE_P_DIGEST: Final = (
    "p-logical:72091424e67812b8b7e9efd245943a696027ed2da7cdff7d3f1c714ae44ffb1c"
)
RELEASE_J0_DIGEST: Final = (
    "j0:65dd269884a737a6b76dd263164984ea257c97865a4d88abbaa1a9e5ad87245d"
)
RELEASE_M0_DIGEST: Final = (
    "m0:1302d43f51362ac3a104b125beac10a205e7fa0f585b26eb19ac19537aa574c6"
)
RELEASE_ENTRYPOINT: Final = "arc3-completion-product"
RELEASE_ENTRYPOINT_TARGET: Final = "arc3_agi_agent.product_runner:main"
RELEASE_DISTRIBUTION: Final = "arc3-completion-agent-release"
RELEASE_VERSION: Final = "0.1.0"
ACTION_BUDGET: Final = 4096
OFFICIAL_PINNED_NOTEBOOK: Final = (
    "inversion/arc3-sample-submission-random-agent"
)
OFFICIAL_PINNED_NOTEBOOK_SOURCE_SHA256: Final = (
    "b955a6871226173bc407641f14316583115c5930f27fbc204ab262b92dda8ad6"
)
OFFICIAL_PLACEHOLDER_PARQUET_SHA256: Final = (
    "688e716e8f9ad967f6211a3796070b69c74a5adb5ce93e9f1c0ba77701ea3194"
)
OFFICIAL_PLACEHOLDER_PARQUET_SIZE: Final = 2648
OFFICIAL_PLACEHOLDER_PARQUET_ZLIB_B64: Final = (
    "eNq9Vl1v4kYUHUiWJG20yka1ZUt5QEhBrZRNsQnpehVVskn5SCG7sBu+2gp5bENMbEOxgThRqj5V"
    "far6A/pD+tDH/o/uT+ncsXEIbFZaqaqFPPY5d865M3euxWu5LjDrzFNmt8LEGbSL0Aa3hhASuhkG"
    "MbsMe0DgHSbBJPaO0edrBObg9uwZidlKxsk9HovFEZH4hHk6l3iyEwOJ9wjEBC4mrExG4A9xiMZx"
    "sRj5sSQaRhq9wYXRxGiH+WxutLkHRnAte3Gbc+b+iSi+B11dCv99DnEJV7s0bJXZRMz2fpxLjIez"
    "rqnvo8oeuAG00VdtYwFDBPvUcPTusNcFiigR5ImrDccGYuP8Hl9Joz1mm8+hxA4/V2TibJz9if0l"
    "lj5Oby7vMX9A1osYukU7ZDhhE3yCTyNIdlFrngoVG7M36T9j6d9iixu+qhR/oIT4/QTiH+RPxd6y"
    "rfSv8ZOVkvBkCtU7+WJRZj1MKFg1Vfgrxv4dS/++ln4X/7iqrKQcObE/r7Px9Cb7xzoJ4hIj1dFV"
    "l/tn/TZlOrpx3dWG1sR23NTL5Hc/HCRTwWuXcsYSSl9vUw5ZL3lKBTVJEbpnGpbeXcUDs67njygx"
    "cUxtqBvAOBN75EfEEA8MzQPcNjxVVz2VoM7Esu4Okvd+Yd1WDReI/9ZxocCrrkvkkjMeDq1V2zn6"
    "IVN6GlbtInjJyHS846NVpwhetoJyqp43NvHEowW+vYMCjw3VG47hNWWZeKyOfVAZ+eqYlBN0psbY"
    "NYcOoGL2MHMopO7uk1kkD7OH2dQd4rblev1V82XwaeDebX0J17F8KstyTQ6ub2X5SFb6ckGW+3K+"
    "TzFFecDPYPwm4s9q+eB9rkL5MowKHSFIcWFQgCm8IPHKV2XbmnSKjaOWeD7FpYaHnar5ylRw682s"
    "X7ZDzJJG2K5bRrFxUx4M+00h45bzZwMsXgu4mQuwrGtiu+B13pSPCefjrN5TmzWzkpfNjm1ZuFjv"
    "PcZrxQLJoXDTytZzWvGC+Mum3syN2qJ0ReLBa6I3hZnRkDJGS7HAr2xLpmo3Bnqe8l6nVb8kGpk2"
    "6BdzAi5eS5U8rC93iZuBZkck/g1p1Anm2Gqz4XYK0qTdFEJNncQ2/v+8mrmrlijZLVGn2CN7ZpEa"
    "9LDY6dF1BP6zNpnbbp339JI1C+NMLEpu2YT6Eb+WklvMv21LU/wRuWnkXGj2ozndkL3wP5DLCDs1"
    "8Tz/2F5ZE/20nQlyFSy9WCDz65fAYafh4pKggy/BMpptmXqrbmk+0S15EsWzZxbhppoJGDl/RcvU"
    "7IJvBN4zo1nwNVvKUn2nY2nO+QiLR3Rd1UF1Us0fXZedzMPc7YavidYUg2a+7Fcgzj+TZLkN/RPG"
    "VcMmy7vQSpocdR69669JP0P71cq1sAkXWpuowGPpfIBJ/vBOGrEK/anMwlC4LijjwqeB9v6lHFkp"
    "UZBcgdvS+ZGH4C8NyO0FpFSgSSn9+ywjKcWBs98SrSu5SuNrkBzJpwj8aWgWTapd0EWUltcD0qWz"
    "qS6Q3oqm3POIS47U8Y8Tw3uujUbP6YczGX4Yk8Enk4c/P9EPfb2F0Gvyn/JfSYasXQ=="
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_object(path: Path) -> tuple[dict[str, object], bytes]:
    payload = path.read_bytes()
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise TypeError("KAGGLE_CONTRACT_JSON_OBJECT_REQUIRED:" + path.as_posix())
    return {str(key): item for key, item in value.items()}, payload


def _logical_seal(value: dict[str, object]) -> str:
    material = dict(value)
    material.pop("logical_content_sha256", None)
    return _sha256(
        json.dumps(
            material,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )


def _require_object(value: object, error: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(error)
    return {str(key): item for key, item in value.items()}


def load_package_contract() -> dict[str, object]:
    wheelhouse, wheelhouse_payload = _load_object(WHEELHOUSE_MANIFEST_PATH)
    p02, p02_payload = _load_object(M4_P02_REPORT_PATH)
    p04, p04_payload = _load_object(M4_P04_REPORT_PATH)
    release_payload = RELEASE_WHEEL_PATH.read_bytes()
    wheelhouse_dataset = _require_object(
        wheelhouse.get("dataset"),
        "KAGGLE_WHEELHOUSE_DATASET_CONTRACT_INVALID",
    )
    wheelhouse_release = _require_object(
        wheelhouse.get("release_wheel"),
        "KAGGLE_WHEELHOUSE_RELEASE_CONTRACT_INVALID",
    )
    p04_exit = _require_object(
        p04.get("exit_audit"),
        "KAGGLE_M4_P04_EXIT_AUDIT_INVALID",
    )
    p04_sources = _require_object(
        p04.get("source_bindings"),
        "KAGGLE_M4_P04_SOURCE_BINDINGS_INVALID",
    )
    p04_release = _require_object(
        p04_sources.get("release_wheel"),
        "KAGGLE_M4_P04_RELEASE_BINDING_INVALID",
    )
    failures: list[str] = []
    if wheelhouse.get("status") != "WHEELHOUSE_READY":
        failures.append("WHEELHOUSE_NOT_READY")
    if wheelhouse.get("logical_content_sha256") != _logical_seal(wheelhouse):
        failures.append("WHEELHOUSE_LOGICAL_SEAL_INVALID")
    if wheelhouse_dataset.get("id") != WHEELHOUSE_DATASET_ID:
        failures.append("WHEELHOUSE_DATASET_ID_MISMATCH")
    if wheelhouse.get("dependency_count") != 32:
        failures.append("WHEELHOUSE_DEPENDENCY_COUNT_MISMATCH")
    if wheelhouse.get("file_count") != 33:
        failures.append("WHEELHOUSE_FILE_COUNT_MISMATCH")
    if _sha256(release_payload) != RELEASE_WHEEL_SHA256:
        failures.append("RELEASE_WHEEL_SHA256_MISMATCH")
    if wheelhouse_release.get("sha256") != RELEASE_WHEEL_SHA256:
        failures.append("WHEELHOUSE_RELEASE_WHEEL_MISMATCH")
    if wheelhouse.get("release_package_sha256") != RELEASE_PACKAGE_SHA256:
        failures.append("WHEELHOUSE_RELEASE_PACKAGE_MISMATCH")
    if wheelhouse.get("release_descriptor_sha256") != RELEASE_DESCRIPTOR_SHA256:
        failures.append("WHEELHOUSE_RELEASE_DESCRIPTOR_MISMATCH")
    if p02.get("status") != "M4_P02_PASS":
        failures.append("M4_P02_NOT_PASS")
    if p04.get("status") != "M4_P04_PASS":
        failures.append("M4_P04_NOT_PASS")
    if p04_exit.get("same_release_artifact") is not True:
        failures.append("M4_P04_SAME_RELEASE_NOT_ESTABLISHED")
    if p04_release.get("sha256") != RELEASE_WHEEL_SHA256:
        failures.append("M4_P04_RELEASE_WHEEL_MISMATCH")
    if failures:
        raise RuntimeError(";".join(failures))
    return {
        "wheelhouse": wheelhouse,
        "wheelhouse_manifest_sha256": _sha256(wheelhouse_payload),
        "M4_P02_sha256": _sha256(p02_payload),
        "M4_P04_sha256": _sha256(p04_payload),
        "release_wheel_size_bytes": len(release_payload),
    }


def _code_cell(source: str, *, cell_id: str) -> dict[str, object]:
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": cell_id,
        "metadata": {"trusted": True},
        "outputs": [],
        "source": source,
    }


def build_notebook() -> tuple[dict[str, object], dict[str, object]]:
    contract = load_package_contract()
    wheelhouse = contract["wheelhouse"]
    if not isinstance(wheelhouse, dict):
        raise TypeError("KAGGLE_WHEELHOUSE_CONTRACT_INVALID")
    expected_files = wheelhouse.get("all_file_sha256")
    dependency_rows = wheelhouse.get("dependency_wheels")
    release_row = wheelhouse.get("release_wheel")
    if not isinstance(expected_files, dict) or not isinstance(dependency_rows, list):
        raise TypeError("KAGGLE_WHEELHOUSE_FILE_CONTRACT_INVALID")
    if not isinstance(release_row, dict):
        raise TypeError("KAGGLE_RELEASE_WHEEL_CONTRACT_INVALID")
    expected_requirements = tuple(
        str(row["requirement"])
        for row in dependency_rows
        if isinstance(row, dict)
    )
    if len(expected_requirements) != 32:
        raise ValueError("KAGGLE_DEPENDENCY_REQUIREMENT_COUNT_INVALID")
    expected_target_versions = {
        str(row["distribution"]): str(row["version"])
        for row in (*dependency_rows, release_row)
        if isinstance(row, dict)
    }
    if len(expected_target_versions) != 33:
        raise ValueError("KAGGLE_TARGET_DISTRIBUTION_COUNT_INVALID")

    install_cell = _code_cell(
        dedent(
            f"""\
            import base64
            import hashlib
            import importlib.metadata as importlib_metadata
            import json
            import os
            import re
            import subprocess
            import sys
            import traceback
            import zlib
            from pathlib import Path

            competition_rerun = bool(os.getenv("KAGGLE_IS_COMPETITION_RERUN"))
            wheelhouse_ready = False
            install_status = {{
                "schema_version": "arc3-m4-p05-install-status-v2",
                "status": "NOT_STARTED",
                "dataset_id": {WHEELHOUSE_DATASET_ID!r},
                "dataset_source": {WHEELHOUSE_DATASET_SOURCE!r},
                "release_wheel_sha256": {RELEASE_WHEEL_SHA256!r},
                "dependency_count": 32,
                "runtime_environment": None,
                "resolved_mount": None,
                "visible_input_entries": [],
                "error_type": None,
                "error_message": None,
            }}
            if competition_rerun:
                fallback_path = Path("/kaggle/working/submission.parquet")
                fallback_path.parent.mkdir(parents=True, exist_ok=True)
                fallback_bytes = zlib.decompress(
                    base64.b64decode({OFFICIAL_PLACEHOLDER_PARQUET_ZLIB_B64!r})
                )
                assert len(fallback_bytes) == {OFFICIAL_PLACEHOLDER_PARQUET_SIZE}
                assert hashlib.sha256(fallback_bytes).hexdigest() == {OFFICIAL_PLACEHOLDER_PARQUET_SHA256!r}
                fallback_path.write_bytes(fallback_bytes)
                print({{
                    "preexecution_fallback": str(fallback_path),
                    "fallback_size_bytes": fallback_path.stat().st_size,
                    "fallback_sha256": hashlib.sha256(fallback_path.read_bytes()).hexdigest(),
                }})

            try:
                input_root = Path({WHEELHOUSE_INPUT_ROOT!r})
                preferred_root = Path({WHEELHOUSE_MOUNT!r})
                manifest_filename = {WHEELHOUSE_MANIFEST_FILENAME!r}
                expected_manifest_sha256 = {str(contract['wheelhouse_manifest_sha256'])!r}
                if input_root.is_dir():
                    install_status["visible_input_entries"] = sorted(
                        path.name for path in input_root.iterdir()
                    )[:200]
                candidate_roots = []
                if preferred_root.is_dir():
                    candidate_roots.append(preferred_root)
                if input_root.is_dir():
                    for pattern in (
                        "*/" + manifest_filename,
                        "*/*/" + manifest_filename,
                        "*/*/*/" + manifest_filename,
                    ):
                        for manifest_candidate in sorted(input_root.glob(pattern)):
                            candidate_root = manifest_candidate.parent
                            if candidate_root not in candidate_roots:
                                candidate_roots.append(candidate_root)
                verified_roots = []
                for candidate_root in candidate_roots:
                    manifest_candidate = candidate_root / manifest_filename
                    if not manifest_candidate.is_file():
                        continue
                    if hashlib.sha256(manifest_candidate.read_bytes()).hexdigest() == expected_manifest_sha256:
                        verified_roots.append(candidate_root)
                if not verified_roots:
                    raise FileNotFoundError(
                        "ARC3 frozen wheelhouse dataset is missing or unverified: "
                        + json.dumps({{
                            "dataset_source": {WHEELHOUSE_DATASET_SOURCE!r},
                            "preferred_mount": str(preferred_root),
                            "visible_input_entries": install_status["visible_input_entries"],
                            "candidate_roots": [str(path) for path in candidate_roots],
                        }}, sort_keys=True)
                    )
                if len(verified_roots) != 1:
                    raise RuntimeError(
                        "ARC3 frozen wheelhouse mount is ambiguous: "
                        + json.dumps([str(path) for path in verified_roots])
                    )
                wheelhouse_root = verified_roots[0]
                install_status["resolved_mount"] = str(wheelhouse_root)
                expected_sha256 = {dict(expected_files)!r}
                expected_wheels = set(expected_sha256)
                actual_wheels = {{path.name for path in wheelhouse_root.glob("*.whl")}}
                if actual_wheels != expected_wheels:
                    raise RuntimeError(
                        "ARC3 frozen wheelhouse file set mismatch: "
                        + json.dumps({{
                            "missing": sorted(expected_wheels - actual_wheels),
                            "unexpected": sorted(actual_wheels - expected_wheels),
                        }}, sort_keys=True)
                    )
                for filename, expected_digest in sorted(expected_sha256.items()):
                    payload = (wheelhouse_root / filename).read_bytes()
                    actual_digest = hashlib.sha256(payload).hexdigest()
                    if actual_digest != expected_digest:
                        raise RuntimeError(
                            "ARC3 frozen wheel hash mismatch: " + filename
                        )
                manifest_path = wheelhouse_root / manifest_filename
                manifest_payload = manifest_path.read_bytes()
                if hashlib.sha256(manifest_payload).hexdigest() != expected_manifest_sha256:
                    raise RuntimeError("ARC3 wheelhouse manifest hash mismatch")
                release_wheel = wheelhouse_root / {str(release_row['filename'])!r}
                runtime_environment = Path("/tmp/arc3_runtime_env")
                if runtime_environment.exists():
                    raise RuntimeError(
                        "ARC3 isolated runtime target already exists: "
                        + str(runtime_environment)
                    )
                install_wheels = [
                    str(wheelhouse_root / filename)
                    for filename in sorted(expected_wheels)
                ]
                subprocess.check_call([
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    "--no-index",
                    "--no-cache-dir",
                    "--no-compile",
                    "--no-deps",
                    "--target",
                    str(runtime_environment),
                    "--force-reinstall",
                    *install_wheels,
                ])
                expected_target_versions = {expected_target_versions!r}
                observed_target_versions = {{}}
                for distribution in importlib_metadata.distributions(
                    path=[str(runtime_environment)]
                ):
                    raw_name = str(distribution.metadata.get("Name", ""))
                    canonical_name = re.sub(r"[-_.]+", "-", raw_name).casefold()
                    if canonical_name in observed_target_versions:
                        raise RuntimeError(
                            "ARC3 isolated runtime duplicate distribution: "
                            + canonical_name
                        )
                    observed_target_versions[canonical_name] = distribution.version
                if observed_target_versions != expected_target_versions:
                    raise RuntimeError(
                        "ARC3 isolated runtime distribution mismatch: "
                        + json.dumps({{
                            "expected": expected_target_versions,
                            "observed": observed_target_versions,
                        }}, sort_keys=True)
                    )
                runtime_bin = runtime_environment / "bin"
                release_entrypoint = runtime_bin / {RELEASE_ENTRYPOINT!r}
                if not release_entrypoint.is_file():
                    raise RuntimeError(
                        "ARC3 isolated runtime entrypoint is missing: "
                        + str(release_entrypoint)
                    )
                sys.path.insert(0, str(runtime_environment))
                os.environ["PYTHONPATH"] = str(runtime_environment)
                os.environ["PATH"] = str(runtime_bin) + os.pathsep + os.environ.get("PATH", "")
                arc3_runtime_environment = runtime_environment
                wheelhouse_ready = True
                install_status["status"] = "COMPLETE"
                install_status["verified_wheel_count"] = len(actual_wheels)
                install_status["installed_distribution_count"] = len(observed_target_versions)
                install_status["runtime_environment"] = str(runtime_environment)
                install_status["entrypoint"] = str(release_entrypoint)
                install_status["wheelhouse_manifest_sha256"] = hashlib.sha256(manifest_payload).hexdigest()
            except Exception as error:
                install_status["status"] = "INSTALL_EXCEPTION"
                install_status["error_type"] = type(error).__name__
                install_status["error_message"] = str(error)[:2000]
                traceback.print_exc()
                if not competition_rerun:
                    raise
            finally:
                install_status_path = Path("/kaggle/working/arc3_install_status.json")
                try:
                    install_status_path.write_text(
                        json.dumps(install_status, sort_keys=True) + "\\n",
                        encoding="utf-8",
                    )
                except Exception:
                    traceback.print_exc()
                print("ARC3 install status: " + json.dumps(install_status, sort_keys=True))
            """
        ),
        cell_id="install-exact-frozen-wheelhouse",
    )
    payload_cell = _code_cell(
        dedent(
            f"""\
            import importlib.metadata as metadata
            import json
            import os
            import sys
            import traceback
            from pathlib import Path

            from packaging.requirements import Requirement
            from packaging.utils import canonicalize_name

            competition_rerun = bool(os.getenv("KAGGLE_IS_COMPETITION_RERUN"))
            release_ready = False
            payload_status = {{
                "schema_version": "arc3-m4-p05-release-boot-status-v1",
                "status": "NOT_STARTED",
                "error_type": None,
                "error_message": None,
            }}
            try:
                if not globals().get("wheelhouse_ready", False):
                    raise RuntimeError("ARC3 exact frozen wheelhouse was not installed")
                runtime_environment = globals().get("arc3_runtime_environment")
                if not isinstance(runtime_environment, Path):
                    raise RuntimeError("ARC3 isolated runtime environment is unavailable")
                if tuple(sys.version_info[:2]) != (3, 12):
                    raise RuntimeError("ARC3 release requires CPython 3.12")
                from agents.templates.arc3_completion_agent import ARC3CompletionAgent
                from arc3_agi_agent.product_release import load_default_product_release_bundle
                from arc3_agi_agent.product_runner import create_product_session

                target_distributions = {{
                    canonicalize_name(str(item.metadata.get("Name", ""))): item
                    for item in metadata.distributions(path=[str(runtime_environment)])
                }}
                distribution = target_distributions.get({RELEASE_DISTRIBUTION!r})
                if distribution is None:
                    raise RuntimeError("ARC3 release distribution is missing from isolated runtime")
                if distribution.version != {RELEASE_VERSION!r}:
                    raise RuntimeError("ARC3 release distribution version mismatch")
                requirements = tuple(distribution.requires or ())
                expected_requirements = {expected_requirements!r}
                if tuple(sorted(requirements)) != tuple(sorted(expected_requirements)):
                    raise RuntimeError("ARC3 release dependency metadata mismatch")
                dependency_mismatches = []
                for raw_requirement in requirements:
                    requirement = Requirement(raw_requirement)
                    dependency = target_distributions.get(
                        canonicalize_name(requirement.name)
                    )
                    if dependency is None:
                        dependency_mismatches.append(
                            f"{{requirement.name}}:MISSING:{{requirement.specifier}}"
                        )
                        continue
                    installed_version = dependency.version
                    if installed_version not in requirement.specifier:
                        dependency_mismatches.append(
                            f"{{requirement.name}}:{{installed_version}}:{{requirement.specifier}}"
                        )
                if dependency_mismatches:
                    raise RuntimeError(
                        "ARC3 frozen dependency mismatch: " + ",".join(dependency_mismatches)
                    )
                entrypoints = tuple(
                    entry
                    for entry in distribution.entry_points
                    if entry.group == "console_scripts"
                    and entry.name == {RELEASE_ENTRYPOINT!r}
                )
                if len(entrypoints) != 1 or entrypoints[0].value != {RELEASE_ENTRYPOINT_TARGET!r}:
                    raise RuntimeError("ARC3 frozen entrypoint mismatch")
                release = load_default_product_release_bundle()
                session = create_product_session(
                    action_budget={ACTION_BUDGET},
                    mode="VALIDATION",
                    initial_state=release.initial_state,
                )
                observed = {{
                    "release_bundle_id": release.descriptor["product_bundle_id"],
                    "release_bundle_stage": release.descriptor["asset_stage"],
                    "release_bundle_logical_digest": release.logical_digest,
                    "release_package_sha256": release.package_sha256,
                    "initial_state_logical_digest": release.initial_state.logical_digest,
                    "p_logical_digest": release.initial_state.p_bundle.logical_digest(),
                    "j0_digest": release.descriptor["j0_digest"],
                    "m0_digest": release.descriptor["m0_digest"],
                    "runtime_identity_digest": session.runtime_identity.digest(),
                    "entrypoint_count": len(entrypoints),
                    "entrypoint_target": entrypoints[0].value,
                    "dependency_pin_count": len(requirements),
                    "dependency_pin_mismatch_count": len(dependency_mismatches),
                    "state_owner_violation_count": len(session.state_owner_violations()),
                    "agent_class": ARC3CompletionAgent.__name__,
                    "action_budget": session.resource_contract.action_budget_per_episode,
                }}
                expected = {{
                    "release_bundle_id": {RELEASE_BUNDLE_ID!r},
                    "release_bundle_stage": "RELEASE_FROZEN",
                    "release_bundle_logical_digest": {RELEASE_BUNDLE_LOGICAL_DIGEST!r},
                    "release_package_sha256": {RELEASE_PACKAGE_SHA256!r},
                    "initial_state_logical_digest": {RELEASE_INITIAL_STATE_DIGEST!r},
                    "p_logical_digest": {RELEASE_P_DIGEST!r},
                    "j0_digest": {RELEASE_J0_DIGEST!r},
                    "m0_digest": {RELEASE_M0_DIGEST!r},
                    "runtime_identity_digest": {RELEASE_RUNTIME_IDENTITY!r},
                    "entrypoint_count": 1,
                    "entrypoint_target": {RELEASE_ENTRYPOINT_TARGET!r},
                    "dependency_pin_count": 32,
                    "dependency_pin_mismatch_count": 0,
                    "state_owner_violation_count": 0,
                    "agent_class": "ARC3CompletionAgent",
                    "action_budget": {ACTION_BUDGET},
                }}
                if observed != expected:
                    raise RuntimeError(
                        "ARC3 frozen release identity mismatch: "
                        + json.dumps({{"expected": expected, "observed": observed}}, sort_keys=True)
                    )
                release_ready = True
                payload_status.update(observed)
                payload_status["status"] = "COMPLETE"
            except Exception as error:
                payload_status["status"] = "BOOT_EXCEPTION"
                payload_status["error_type"] = type(error).__name__
                payload_status["error_message"] = str(error)[:2000]
                traceback.print_exc()
                if not competition_rerun:
                    raise
            finally:
                payload_status_path = Path("/kaggle/working/arc3_payload_status.json")
                try:
                    payload_status_path.write_text(
                        json.dumps(payload_status, sort_keys=True) + "\\n",
                        encoding="utf-8",
                    )
                except Exception:
                    traceback.print_exc()
                print("ARC3 release boot status: " + json.dumps(payload_status, sort_keys=True))
            """
        ),
        cell_id="verify-exact-release-identity",
    )
    run_cell = _code_cell(
        dedent(
            f"""\
            import json
            import os
            import shutil
            import subprocess
            import sys
            import time
            import traceback
            import urllib.error
            import urllib.request
            from pathlib import Path

            if os.getenv("KAGGLE_IS_COMPETITION_RERUN"):
                runtime_status_path = Path("/kaggle/working/arc3_runtime_status.json")
                product_report_path = Path("/kaggle/working/arc3_product_report.json")
                runtime_status = {{
                    "schema_version": "arc3-m4-p05-private-runtime-status-v1",
                    "status": "STARTED",
                    "runner_returncode": None,
                    "scorecard_open_count": None,
                    "scorecard_close_count": None,
                    "scorecard_closed": None,
                    "error_type": None,
                    "error_message": None,
                }}
                try:
                    if not globals().get("release_ready", False):
                        raise RuntimeError("ARC3 exact frozen release is unavailable")
                    gateway = "http://gateway:8001/api/games"
                    deadline = time.time() + 600
                    while True:
                        try:
                            with urllib.request.urlopen(gateway, timeout=10) as response:
                                if response.status < 500:
                                    break
                        except (urllib.error.URLError, TimeoutError):
                            pass
                        if time.time() >= deadline:
                            raise TimeoutError(
                                "ARC3 competition gateway did not become ready within 600 seconds"
                            )
                        time.sleep(5)
                    entrypoint = shutil.which({RELEASE_ENTRYPOINT!r})
                    if entrypoint is None:
                        raise FileNotFoundError("ARC3 frozen console entrypoint is missing")
                    run_env = os.environ.copy()
                    run_env.update({{
                        "SCHEME": "http",
                        "HOST": "gateway",
                        "PORT": "8001",
                        "ARC_API_KEY": "test-key-123",
                        "ARC_BASE_URL": "http://gateway:8001/",
                        "OPERATION_MODE": "competition",
                        "ENVIRONMENTS_DIR": "",
                        "RECORDINGS_DIR": "/kaggle/working/server_recording",
                        "MPLBACKEND": "agg",
                    }})
                    completed_process = subprocess.run(
                        [
                            entrypoint,
                            "--mode",
                            "competition",
                            "--release-frozen",
                            "--action-budget",
                            {str(ACTION_BUDGET)!r},
                            "--report",
                            str(product_report_path),
                        ],
                        cwd="/kaggle/working",
                        env=run_env,
                        check=False,
                    )
                    runtime_status["runner_returncode"] = completed_process.returncode
                    if completed_process.returncode != 0:
                        raise RuntimeError(
                            f"ARC3 frozen product runner returned {{completed_process.returncode}}"
                        )
                    product_report = json.loads(product_report_path.read_text(encoding="utf-8"))
                    lifecycle = {{
                        "orchestration_mode": product_report.get("orchestration_mode"),
                        "active_agent_peak": product_report.get("active_agent_peak"),
                        "shared_session_count": product_report.get("shared_session_count"),
                        "scorecard_open_count": product_report.get("scorecard_open_count"),
                        "scorecard_close_count": product_report.get("scorecard_close_count"),
                        "scorecard_closed": product_report.get("scorecard_closed"),
                        "release_loaded": product_report.get("product_release_bundle_loaded"),
                        "release_stage": product_report.get("product_bundle_stage"),
                        "release_package_sha256": product_report.get("product_release_bundle_sha256"),
                        "runtime_policy_changed": product_report.get("runtime_policy_changed"),
                    }}
                    expected_lifecycle = {{
                        "orchestration_mode": "SEQUENTIAL_SINGLE_ACTIVE_GAME",
                        "active_agent_peak": 1,
                        "shared_session_count": 1,
                        "scorecard_open_count": 1,
                        "scorecard_close_count": 1,
                        "scorecard_closed": True,
                        "release_loaded": True,
                        "release_stage": "RELEASE_FROZEN",
                        "release_package_sha256": {RELEASE_PACKAGE_SHA256!r},
                        "runtime_policy_changed": False,
                    }}
                    if lifecycle != expected_lifecycle:
                        raise RuntimeError(
                            "ARC3 sequential scorecard lifecycle mismatch: "
                            + json.dumps({{"expected": expected_lifecycle, "observed": lifecycle}}, sort_keys=True)
                        )
                    runtime_status.update(lifecycle)
                    runtime_status["status"] = "COMPLETE"
                except Exception as error:
                    runtime_status["status"] = "RUNTIME_EXCEPTION"
                    runtime_status["error_type"] = type(error).__name__
                    runtime_status["error_message"] = str(error)[:2000]
                    traceback.print_exc()
                finally:
                    try:
                        runtime_status_path.write_text(
                            json.dumps(runtime_status, sort_keys=True) + "\\n",
                            encoding="utf-8",
                        )
                    except Exception:
                        traceback.print_exc()
                    print("ARC3 private runtime status: " + json.dumps(runtime_status, sort_keys=True))
            """
        ),
        cell_id="execute-frozen-product-runtime",
    )
    placeholder_cell = _code_cell(
        dedent(
            f"""\
            # Normal run only: produce and inspect the official ARC-AGI-3 placeholder.
            import hashlib
            import json
            import os
            from pathlib import Path

            import pandas as pd

            if not os.getenv("KAGGLE_IS_COMPETITION_RERUN"):
                if not globals().get("release_ready", False):
                    raise RuntimeError("ARC3 normal run release verification did not complete")
                output_path = Path("/kaggle/working/submission.parquet")
                submission = pd.DataFrame(
                    data=[["1_0", "1", True, 1]],
                    columns=["row_id", "game_id", "end_of_game", "score"],
                )
                submission.to_parquet(output_path, index=False)
                output_payload = output_path.read_bytes()
                normal_status = {{
                    "schema_version": "arc3-m4-p05-normal-run-status-v1",
                    "status": "COMPLETE",
                    "release_wheel_sha256": {RELEASE_WHEEL_SHA256!r},
                    "release_package_sha256": {RELEASE_PACKAGE_SHA256!r},
                    "runtime_identity_digest": {RELEASE_RUNTIME_IDENTITY!r},
                    "dependency_pin_count": 32,
                    "dependency_pin_mismatch_count": 0,
                    "submission_api_call_count": 0,
                    "output_path": str(output_path),
                    "output_size_bytes": len(output_payload),
                    "output_sha256": hashlib.sha256(output_payload).hexdigest(),
                    "output_columns": list(submission.columns),
                    "output_rows": submission.to_dict(orient="records"),
                }}
                Path("/kaggle/working/arc3_normal_run_status.json").write_text(
                    json.dumps(normal_status, sort_keys=True) + "\\n",
                    encoding="utf-8",
                )
                print("ARC3 normal run status: " + json.dumps(normal_status, sort_keys=True))
            """
        ),
        cell_id="write-official-placeholder",
    )
    notebook: dict[str, object] = {
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "pygments_lexer": "ipython3",
            },
            "kaggle": {
                "accelerator": "none",
                "isGpuEnabled": False,
                "isInternetEnabled": False,
                "language": "python",
                "sourceType": "notebook",
            },
        },
        "nbformat": 4,
        "nbformat_minor": 4,
        "cells": [install_cell, payload_cell, run_cell, placeholder_cell],
    }
    build_report: dict[str, object] = {
        "schema_version": "arc3-rev5-1-m4-p05-kaggle-notebook-build-v1",
        "artifact_type": "M4KaggleNotebookBuildEvidence",
        "point_id": "M4-P05_KAGGLE_PACKAGE_NORMAL_RUN",
        "product_id": "ARC3CompletionAgent",
        "asset_stage": "RELEASE_FROZEN",
        "competition": COMPETITION_SLUG,
        "action_budget_per_game": ACTION_BUDGET,
        "source_bindings": {
            "M4_P02_freeze_sha256": contract["M4_P02_sha256"],
            "M4_P04_same_release_full_sample_sha256": contract["M4_P04_sha256"],
            "wheelhouse_manifest_sha256": contract["wheelhouse_manifest_sha256"],
        },
        "release_artifact": {
            "distribution": RELEASE_DISTRIBUTION,
            "version": RELEASE_VERSION,
            "wheel_filename": release_row["filename"],
            "wheel_sha256": RELEASE_WHEEL_SHA256,
            "wheel_size_bytes": contract["release_wheel_size_bytes"],
            "release_descriptor_sha256": RELEASE_DESCRIPTOR_SHA256,
            "release_package_sha256": RELEASE_PACKAGE_SHA256,
            "release_bundle_id": RELEASE_BUNDLE_ID,
            "release_bundle_logical_digest": RELEASE_BUNDLE_LOGICAL_DIGEST,
            "runtime_identity_digest": RELEASE_RUNTIME_IDENTITY,
            "entrypoint": RELEASE_ENTRYPOINT,
            "entrypoint_target": RELEASE_ENTRYPOINT_TARGET,
        },
        "dependency_transport": {
            "dataset_id": WHEELHOUSE_DATASET_ID,
            "dataset_source": WHEELHOUSE_DATASET_SOURCE,
            "dataset_version": WHEELHOUSE_DATASET_VERSION,
            "dataset_mount": WHEELHOUSE_MOUNT,
            "mount_resolution": "MANIFEST_SHA256_UNIQUE",
            "runtime_environment": "/tmp/arc3_runtime_env",
            "runtime_environment_persisted_as_output": False,
            "dependency_count": 32,
            "wheel_file_count": 33,
            "wheelhouse_logical_content_sha256": wheelhouse[
                "logical_content_sha256"
            ],
            "runtime_network_required": False,
            "pip_resolution": "EXPLICIT_33_WHEELS_NO_DEPS_ISOLATED_TARGET",
        },
        "official_contract_basis": {
            "pinned_notebook": OFFICIAL_PINNED_NOTEBOOK,
            "pinned_notebook_source_sha256": OFFICIAL_PINNED_NOTEBOOK_SOURCE_SHA256,
            "competition_data": (
                "https://www.kaggle.com/competitions/"
                + COMPETITION_SLUG
                + "/data"
            ),
            "competition_mode": "https://docs.arcprize.org/toolkit/competition_mode",
            "gateway": "http://gateway:8001/api/games",
            "code_cell_count": 4,
        },
        "preexecution_fallback": {
            "source": "official pinned Notebook normal-run output",
            "sha256": OFFICIAL_PLACEHOLDER_PARQUET_SHA256,
            "size_bytes": OFFICIAL_PLACEHOLDER_PARQUET_SIZE,
        },
        "notebook_cell_count": 4,
        "submission_api_call_count": 0,
        "runtime_policy_changed": False,
    }
    return notebook, build_report


def build_metadata(*, username: str, notebook_slug: str) -> dict[str, object]:
    return {
        "id": f"{username}/{notebook_slug}",
        "title": "ARC3CompletionAgent rev5.1 frozen release",
        "code_file": "submission.ipynb",
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": False,
        "enable_tpu": False,
        "enable_internet": False,
        "keywords": [],
        "dataset_sources": [WHEELHOUSE_DATASET_SOURCE],
        "kernel_sources": [],
        "competition_sources": [COMPETITION_SLUG],
        "model_sources": [],
    }


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default=os.getenv("KAGGLE_USERNAME", DEFAULT_USERNAME))
    parser.add_argument("--notebook-slug", default=DEFAULT_NOTEBOOK_SLUG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    output_dir = arguments.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    notebook, build_report = build_notebook()
    metadata = build_metadata(
        username=str(arguments.username),
        notebook_slug=str(arguments.notebook_slug),
    )
    notebook_data = (json.dumps(notebook, indent=1, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )
    metadata_data = (json.dumps(metadata, indent=2, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )
    (output_dir / "submission.ipynb").write_bytes(notebook_data)
    (output_dir / "kernel-metadata.json").write_bytes(metadata_data)
    build_report["notebook_sha256"] = _sha256(notebook_data)
    build_report["notebook_size_bytes"] = len(notebook_data)
    build_report["metadata_sha256"] = _sha256(metadata_data)
    build_report["metadata"] = metadata
    report_data = (json.dumps(build_report, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    (output_dir / "build-report.json").write_bytes(report_data)
    print(
        json.dumps(
            {
                "notebook": str(output_dir / "submission.ipynb"),
                "notebook_sha256": build_report["notebook_sha256"],
                "notebook_size_bytes": build_report["notebook_size_bytes"],
                "release_wheel_sha256": RELEASE_WHEEL_SHA256,
                "wheelhouse_dataset_id": WHEELHOUSE_DATASET_ID,
                "metadata_id": metadata["id"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
