"""Cryptographic provenance: what can and cannot be established.

A SHA-256 proves the bytes have not changed since *you* hashed them. A C2PA
manifest proves a signed assertion set is intact and trusted, not that the scene
is real. Absence of a manifest is normal and is not evidence of tampering.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as fh:
        while True:
            block = fh.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def c2pa_check(path: Path) -> dict[str, Any]:
    """Check Content Credentials with c2patool when it is installed."""
    tool = shutil.which("c2patool")
    if tool is None:
        return {
            "status": "not_checked",
            "reason": "c2patool is not installed",
            "note": "absence of a manifest is normal and is not evidence of tampering",
        }
    try:
        proc = subprocess.run(
            [tool, str(path), "--info"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}
    out = (proc.stdout or "") + (proc.stderr or "")
    try:
        parsed = json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else None
    except json.JSONDecodeError:
        parsed = None
    return {
        "status": "checked",
        "exit_code": proc.returncode,
        "manifest": parsed,
        "raw": out[:4000],
        "note": "a valid manifest proves integrity and a signer assertion, not that the scene is real",
    }


def provenance_report(path: Path) -> dict[str, Any]:
    path = Path(path)
    return {
        "path": str(path.resolve()),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "c2pa": c2pa_check(path),
        "limits": [
            "A hash proves integrity from the moment of hashing, not the file's age.",
            "Metadata is writable by design and cannot by itself support a claim.",
            "A valid C2PA manifest does not prove the scene is real or the location true.",
        ],
    }
