"""Download pinned public weights once; verify every LFS file before offline use."""

import argparse
import hashlib
import json
import os
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

MANIFEST_DIR = Path(os.getenv("QWEN_MANIFEST_DIR", Path(__file__).parent))


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def verify(root):
    expected = json.loads((MANIFEST_DIR / "model-manifest.json").read_text())
    actual = json.loads((root / "model-manifest.json").read_text())
    if actual != expected:
        raise RuntimeError("Downloaded model revisions do not match runtime manifest")
    records = json.loads((MANIFEST_DIR / "model-artifacts.json").read_text())
    if json.loads((root / "artifacts.json").read_text()) != records:
        raise RuntimeError("Artifact manifest differs from pinned runtime checksums")
    if not records or not any(x.endswith(".safetensors") for x in records):
        raise RuntimeError("Weight checksum manifest is empty")
    for filename, expected in records.items():
        if digest(root / filename) != expected:
            raise RuntimeError(f"SHA256 mismatch: {filename}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        verify(args.root)
        return
    manifest = json.loads((MANIFEST_DIR / "model-manifest.json").read_text())
    artifacts = {}
    for name, model in manifest.items():
        info = HfApi().model_info(
            model["repository"], revision=model["revision"], files_metadata=True
        )
        assert info.sha == model["revision"]
        files = [
            f
            for f in info.siblings
            if f.rfilename.endswith((".json", ".safetensors", ".jinja", ".txt", ".model"))
            or f.rfilename in ("LICENSE", "README.md", "merges.txt")
        ]
        snapshot_download(
            model["repository"],
            revision=model["revision"],
            local_dir=args.root / name,
            allow_patterns=[f.rfilename for f in files],
            max_workers=4,
        )
        for file in files:
            path = args.root / name / file.rfilename
            actual = digest(path)
            if file.lfs and actual != file.lfs.sha256:
                raise RuntimeError(f"Hub LFS SHA256 mismatch: {file.rfilename}")
            artifacts[f"{name}/{file.rfilename}"] = actual
    (args.root / "artifacts.json").write_text(json.dumps(artifacts, indent=2) + "\n")
    (args.root / "model-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    verify(args.root)


if __name__ == "__main__":
    main()
