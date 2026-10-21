#!/usr/bin/env python3
"""Unpack the VCF MCP package and the OpenAPI specs, then serve.

Specs are mounted as ordered chunks because one ConfigMap cannot hold them.
"""

from __future__ import annotations

import io
import os
import pathlib
import subprocess
import sys
import tarfile


def main() -> None:
    root = pathlib.Path("/tmp/src")
    root.mkdir(parents=True, exist_ok=True)
    tarfile.open("/bundle/package.tar").extractall(root, filter="data")
    parts = sorted(p for p in pathlib.Path("/spec-parts").iterdir() if p.is_file())
    blob = b"".join(p.read_bytes() for p in parts)
    if not blob:
        raise SystemExit("vcf specs not mounted")
    tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz").extractall(root, filter="data")
    spec = root / "specs"
    if not spec.is_dir():
        raise SystemExit("specs dir missing after extract")
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--user",
            "-q",
            "mcp>=2",
            "httpx>=0.27",
            "PyYAML>=6",
            "uvicorn>=0.30",
            "starlette>=0.37",
            "PyJWT[crypto]>=2.8",
        ]
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    env["VCF_MCP_SPEC_DIR"] = str(spec)
    env["PATH"] = env.get("PATH", "") + ":/tmp/.local/bin"
    os.execvpe(sys.executable, [sys.executable, "-m", "vcf_mcp", "serve-http"], env)


if __name__ == "__main__":
    main()
