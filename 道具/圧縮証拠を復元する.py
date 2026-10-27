"""Gitに保存した大きな実行証拠を、元のSHA-256と照合して復元する。"""

from __future__ import annotations

import argparse
import hashlib
import json
import lzma
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "運用/GitHub成果保存/20261027/large-evidence-archives-xz.json"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def within(root: Path, relative: str) -> Path:
    value = Path(relative)
    target = (root / value).resolve()
    if value.is_absolute() or not target.is_relative_to(root):
        raise ValueError("証拠のパスがリポジトリ外を指しています")
    return target


def restore(root: Path, manifest: dict, *, verify_only: bool = False) -> dict:
    root = root.resolve()
    if manifest.get("schema") != "arc3-lossless-git-evidence-archives.v2":
        raise ValueError("未対応のarchive manifestです")
    counts = {"verified": 0, "restored": 0, "existing_verified": 0}
    for entry in manifest["files"]:
        source = within(root, entry["archive_path"])
        target = within(root, entry["original_path"])
        if entry["archive_format"] != "xz" or digest(source) != entry["archive_sha256"]:
            raise ValueError(f"圧縮証拠のhash不一致: {entry['archive_path']}")
        if not verify_only and target.exists():
            if digest(target) != entry["original_sha256"]:
                raise FileExistsError(f"異なる既存ファイルを上書きしません: {entry['original_path']}")
            counts["existing_verified"] += 1
            continue
        temporary = None
        try:
            if not verify_only:
                target.parent.mkdir(parents=True, exist_ok=True)
                temporary = tempfile.NamedTemporaryFile(
                    prefix=".arc3-evidence-", dir=target.parent, delete=False
                )
            h = hashlib.sha256()
            size = 0
            with lzma.open(source, "rb") as stream:
                while block := stream.read(1024 * 1024):
                    h.update(block)
                    size += len(block)
                    if temporary is not None:
                        temporary.write(block)
            if h.hexdigest() != entry["original_sha256"] or size != entry["original_bytes"]:
                raise ValueError(f"復元byteのhash/size不一致: {entry['original_path']}")
            counts["verified"] += 1
            if temporary is not None:
                temporary.close()
                if target.exists():
                    raise FileExistsError(f"復元中にファイルが作成されました: {entry['original_path']}")
                Path(temporary.name).rename(target)
                counts["restored"] += 1
        finally:
            if temporary is not None:
                temporary.close()
                temporary_path = Path(temporary.name).resolve()
                if temporary_path.is_relative_to(root):
                    temporary_path.unlink(missing_ok=True)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    print(json.dumps(restore(ROOT, manifest, verify_only=args.verify_only), ensure_ascii=False))


if __name__ == "__main__":
    main()
