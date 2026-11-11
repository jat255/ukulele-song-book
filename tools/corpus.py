"""Inventory and copy selected, immutable source documents for local evaluation."""

import argparse
import hashlib
import json
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path

from pypdf import PdfReader


@dataclass
class SourceCandidate:
    relative_path: str
    kind: str
    sha256: str


@dataclass
class CorpusSample:
    id: str
    category: str
    relative_path: str
    sha256: str
    pages: list[int]
    expected_observations: str
    verification_status: str
    aliases: list[str] = field(default_factory=list)


@dataclass
class CorpusManifest:
    samples: list[CorpusSample]


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inventory(root: Path) -> list[SourceCandidate]:
    root = root.resolve(strict=True)
    result = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if path.is_symlink():
            if not path.resolve().is_relative_to(root):
                raise ValueError("source symlink escapes root")
            continue
        if path.is_file() and path.suffix.lower() in {".pdf", ".cho", ".chordpro"}:
            result.append(
                SourceCandidate(
                    relative.as_posix(), path.suffix.lower()[1:], file_hash(path)
                )
            )
    return result


def select_corpus(root: Path, manifest: Path, output: Path) -> CorpusManifest:
    root = root.resolve(strict=True)
    if output.resolve().is_relative_to(root):
        raise ValueError("output must be outside source root")
    available = {item.relative_path: item for item in inventory(root)}
    data = json.loads(manifest.read_text(encoding="utf-8"))
    samples = []
    by_hash = {}
    ids = set()
    for entry in data["samples"]:
        sample = CorpusSample(**entry)
        candidate = available.get(sample.relative_path)
        if candidate is None or candidate.sha256 != sample.sha256:
            raise ValueError("missing or changed source")
        if not sample.pages or any(type(p) is not int or p < 1 for p in sample.pages):
            raise ValueError("pages must be positive one-based integers")
        if candidate.kind == "pdf":
            try:
                page_count = len(PdfReader(root / sample.relative_path).pages)
            except Exception as exc:
                raise ValueError("PDF cannot be read") from exc
            if max(sample.pages) > page_count:
                raise ValueError("selected PDF page does not exist")
        if sample.sha256 in by_hash:
            by_hash[sample.sha256].aliases.append(sample.relative_path)
            continue
        if (
            not sample.id
            or sample.id in ids
            or not sample.id.replace("-", "").replace("_", "").isalnum()
        ):
            raise ValueError("invalid or duplicate sample ID")
        ids.add(sample.id)
        samples.append(sample)
        by_hash[sample.sha256] = sample
    output.mkdir(parents=True, exist_ok=True)
    if (output / "manifest.json").is_symlink():
        raise ValueError("unsafe manifest destination")
    for sample in samples:
        source = root / sample.relative_path
        target = output / "originals" / (sample.sha256 + source.suffix.lower())
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink() or target.parent.resolve().is_relative_to(root):
            raise ValueError("unsafe destination")
        shutil.copyfile(source, target)
        if file_hash(target) != sample.sha256 or file_hash(source) != sample.sha256:
            raise ValueError("source changed during copy")
    result = CorpusManifest(samples)
    (output / "manifest.json").write_text(
        json.dumps(asdict(result), indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    inv = sub.add_parser("inventory")
    inv.add_argument("--root", type=Path, required=True)
    select = sub.add_parser("select")
    select.add_argument("--root", type=Path, required=True)
    select.add_argument("--manifest", type=Path, required=True)
    select.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = (
        inventory(args.root)
        if args.command == "inventory"
        else select_corpus(args.root, args.manifest, args.output)
    )
    print(
        json.dumps(
            [asdict(item) for item in result]
            if isinstance(result, list)
            else asdict(result),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
