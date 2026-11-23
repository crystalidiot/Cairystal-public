#!/usr/bin/env python3
"""Inventory executable files by task; never execute them or read old job logs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path


TOOLS = (
    "olex2.exe",
    "shelxt.exe",
    "shelxl.exe",
    "shelxd.exe",
    "shelxs.exe",
    "platon.exe",
    "ciftab.exe",
    "shredcif.exe",
)
PROFILES = {
    "solve": ("shelxt.exe", "shelxl.exe"),
    "solve_d": ("shelxd.exe", "shelxl.exe"),
    "solve_s": ("shelxs.exe", "shelxl.exe"),
    "refine": ("shelxl.exe",),
    "validate": ("platon.exe",),
    "viewer": ("olex2.exe",),
    "bundle": ("olex2.exe", "shelxt.exe", "shelxl.exe", "platon.exe"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def binary_text(path: Path) -> str:
    return path.read_bytes().decode("latin-1", errors="ignore")


def first_match(text: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def detect_version(root: Path, name: str, path: Path) -> str | None:
    if name == "olex2.exe":
        tag = root / "olex2.tag"
        revision = root / "version.txt"
        parts: list[str] = []
        if tag.is_file():
            parts.append(tag.read_text(encoding="utf-8", errors="replace").strip())
        if revision.is_file():
            rev = first_match(
                revision.read_text(encoding="utf-8", errors="replace"),
                (r"SVN Revision No\.\s*(\S+)",),
            )
            if rev:
                parts.append(f"SVN {rev}")
        return ", ".join(parts) or None

    text = binary_text(path)
    patterns = {
        "shelxt.exe": (r"SHELXT(?:\s+|-)(\d{4}/\d+)", r"VERSION\s+(\d{4}/\d+)"),
        "shelxl.exe": (r"SHELXL-(\d{4}/\d+)", r"Version\s+(\d{4}/\d+)"),
        "shelxd.exe": (r"SHELXD(?:\s+|-)(\d{4}/\d+)", r"Version\s+(\d{4}/\d+)"),
        "shelxs.exe": (r"Version\s+(\d{4}/\d+)",),
    }
    if name in patterns:
        return first_match(text, patterns[name])
    # A neighbouring platon.out may be from another binary, job or protected case.
    # Leave the version unknown until a new isolated invocation supplies its banner.
    return None


def probe(root: Path, profile: str = "solve") -> dict:
    if profile not in PROFILES:
        raise ValueError(f"Unknown profile: {profile}")
    root = root.expanduser().resolve()
    report: dict[str, object] = {
        "software_dir": str(root),
        "exists": root.is_dir(),
        "selected_profile": profile,
        "execution_verified": False,
        "tools": [],
        "limitation": (
            "Ready means selected executable files are present and readable only; "
            "versions are hints, not verified runtime banners. This does not test "
            "licences, DLL compatibility, PLATON configuration or scientific results."
        ),
    }
    for name in TOOLS:
        entry: dict[str, object] = {
            "name": name,
            "path": str(root / name),
            "exists": False,
            "readable": False,
            "on_path": shutil.which(name),
            "version": None,
            "version_source": None,
            "error": None,
        }
        try:
            path = root / name
            entry["exists"] = path.is_file()
            if entry["exists"]:
                entry.update(
                    size=path.stat().st_size,
                    sha256=sha256(path),
                    version=detect_version(root, name, path),
                    readable=True,
                )
                if entry["version"]:
                    entry["version_source"] = (
                        "installation_metadata_hint" if name == "olex2.exe"
                        else "embedded_string_hint"
                    )
        except OSError as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
        report["tools"].append(entry)

    available = {e["name"] for e in report["tools"] if e["exists"] and e["readable"]}
    report["profiles"] = {}
    for role, required in PROFILES.items():
        missing = [name for name in required if name not in available]
        report["profiles"][role] = {
            "required": list(required), "missing_or_unreadable": missing,
            "files_ready": report["exists"] and not missing,
        }
    selected = report["profiles"][profile]
    report["missing_required"] = selected["missing_or_unreadable"]
    report["ready"] = selected["files_ready"]
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--software-dir", required=True, type=Path)
    parser.add_argument("--profile", choices=PROFILES, default="solve",
                        help="File requirements only; default: headless SHELXT + SHELXL")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = probe(args.software_dir, args.profile)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Software directory: {report['software_dir']}")
        for item in report["tools"]:
            state = "found" if item["exists"] else "missing"
            version = item.get("version") or "unknown version"
            print(f"- {item['name']}: {state}; {version}")
        print(f"Files ready for {args.profile}: {report['ready']}; execution not tested")
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
