#!/usr/bin/env python3
"""Extract an oras OCI layout into a rootfs directory. No secrets."""

from __future__ import annotations

import gzip
import json
import os
import tarfile
from pathlib import Path


def extract(layout: Path, dest: Path) -> None:
    index = json.loads((layout / "index.json").read_text())
    digest = index["manifests"][0]["digest"].split(":", 1)[1]
    manifest = json.loads((layout / "blobs" / "sha256" / digest).read_text())
    if manifest.get("mediaType", "").endswith("index") or "manifests" in manifest and "layers" not in manifest:
        # platform manifest list
        chosen = None
        for item in manifest.get("manifests") or []:
            plat = item.get("platform") or {}
            if plat.get("os") == "linux" and plat.get("architecture") == "amd64":
                chosen = item["digest"].split(":", 1)[1]
                break
        if not chosen:
            raise SystemExit(f"no amd64 manifest in {layout}")
        manifest = json.loads((layout / "blobs" / "sha256" / chosen).read_text())
    dest.mkdir(parents=True, exist_ok=True)
    for layer in manifest.get("layers") or []:
        blob = layout / "blobs" / "sha256" / layer["digest"].split(":", 1)[1]
        with gzip.open(blob, "rb") as raw:
            with tarfile.open(fileobj=raw, mode="r|") as tar:
                _safe_extract(tar, dest)
        print("layer", layer["digest"][:19], "ok", flush=True)


def _safe_extract(tar: tarfile.TarFile, dest: Path) -> None:
    dest_resolved = dest.resolve()
    for member in tar:
        name = member.name.lstrip("./")
        if not name or name.startswith("/") or ".." in Path(name).parts:
            continue
        # Docker whiteouts delete a file from an earlier layer.
        parent = dest / Path(name).parent
        base = Path(name).name
        if base.startswith(".wh."):
            victim = parent / base[4:]
            if victim.is_symlink() or victim.exists():
                if victim.is_dir() and not victim.is_symlink():
                    import shutil
                    shutil.rmtree(victim, ignore_errors=True)
                else:
                    victim.unlink(missing_ok=True)
            continue
        target_parent = (dest / name).parent.resolve()
        if not str(target_parent).startswith(str(dest_resolved)):
            continue
        try:
            tar.extract(member, dest, set_attrs=False)
        except (OSError, tarfile.TarError):
            continue
        if member.issym() or member.islnk():
            continue
        path = dest / name
        if path.exists():
            try:
                os.chmod(path, member.mode & 0o7777)
            except OSError:
                pass


if __name__ == "__main__":
    import sys

    extract(Path(sys.argv[1]), Path(sys.argv[2]))
