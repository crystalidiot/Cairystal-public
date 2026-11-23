#!/usr/bin/env python3
"""Inspect SHELX input pairs without modifying the source directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path


KEYWORDS = {
    "TITL",
    "CELL",
    "ZERR",
    "LATT",
    "SYMM",
    "SFAC",
    "UNIT",
    "HKLF",
    "TEMP",
}
REQUIRED_INS = {"CELL", "ZERR", "LATT", "SFAC", "UNIT", "HKLF"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def parse_ins(path: Path) -> tuple[dict[str, object], list[str]]:
    directives: dict[str, object] = {"SYMM": []}
    warnings: list[str] = []
    text = path.read_text(encoding="latin-1", errors="replace")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        keyword = line.split(maxsplit=1)[0].upper()
        if keyword not in KEYWORDS:
            continue
        value = line[len(keyword) :].strip()
        if keyword == "SYMM":
            directives["SYMM"].append(value)
        elif keyword not in directives:
            directives[keyword] = value

    missing = sorted(REQUIRED_INS - directives.keys())
    if missing:
        warnings.append("Missing INS directives: " + ", ".join(missing))
    if not directives["SYMM"]:
        warnings.append("No explicit SYMM instructions found; verify that this is intended for the lattice/space group.")
    return directives, warnings


def reflection_after_blank(line: str) -> bool:
    """A data-looking row after a blank end marker makes the HKL extent ambiguous."""
    try:
        indices = tuple(int(line[i:i + 4]) for i in (0, 4, 8))
        return indices != (0, 0, 0) and all(
            math.isfinite(float(line[i:i + 8])) for i in (12, 20))
    except ValueError:
        return False


def reflection_stats(path: Path) -> dict[str, object]:
    line_count = 0
    nonblank_count = 0
    terminator_found = False
    record_count = 0
    format_issue_count = 0
    issue_samples: list[dict[str, object]] = []
    routine_issue = None
    stopped = False
    check_blank_end = False

    def numeric_record(line: str, dimensions: int) -> bool:
        offset = dimensions * 4
        if len(line) < offset + 16:
            return False
        try:
            for start in range(0, offset, 4):
                int(line[start:start + 4])
            values = [float(line[offset:offset + 8]), float(line[offset + 8:offset + 16])]
            batch = line[offset + 16:offset + 20].strip()
            if batch:
                int(batch)
            return all(math.isfinite(value) for value in values)
        except ValueError:
            return False

    with path.open("r", encoding="latin-1", errors="replace") as handle:
        for raw_line in handle:
            line_count += 1
            fields = raw_line.split()
            if fields:
                nonblank_count += 1
            if stopped:
                if check_blank_end and fields:
                    if routine_issue is None and reflection_after_blank(raw_line):
                        routine_issue = {'line': line_count, 'reason': 'reflection_after_blank_terminator'}
                    check_blank_end = False
                continue
            if not fields:
                terminator_found = True
                stopped = True
                check_blank_end = True
                continue
            # Fixed-width formats may have adjacent signs with no whitespace.
            line = raw_line.rstrip("\r\n")
            standard = numeric_record(line, 3)
            if not standard and numeric_record(line, 4):
                issue = "possible_four_index_data_requires_specialist_route"
            else:
                try:
                    zero_indices = all(int(line[start:start + 4]) == 0 for start in (0, 4, 8))
                except ValueError:
                    zero_indices = False
                if zero_indices:
                    terminator_found = True
                    stopped = True
                    continue
                issue = None if standard else "unrecognized_fixed_width_record_requires_review"
            if issue:
                format_issue_count += 1
                if len(issue_samples) < 5:
                    issue_samples.append({"line": line_count, "reason": issue})
            else:
                record_count += 1
                if routine_issue is None:
                    tail = line[28:].split()
                    if float(line[20:28]) <= 0:
                        routine_issue = {'line': line_count, 'reason': 'nonpositive_sigma'}
                    elif len(tail) > 1:
                        routine_issue = {'line': line_count, 'reason': 'additional_reflection_columns'}
                    elif tail and not re.fullmatch(r'[+-]?\d+',tail[0]):
                        routine_issue = {'line': line_count, 'reason': 'unrecognized_batch_column'}
                    elif tail and int(tail[0]) < 0:
                        routine_issue = {'line': line_count, 'reason': 'negative_component_index_requires_review'}
    return {
        "size": path.stat().st_size,
        "line_count": line_count,
        "nonblank_line_count": nonblank_count,
        "terminator_found": terminator_found,
        "standard_record_count": record_count,
        "routine_hkl4_issue": routine_issue,
        "format_issue_count": format_issue_count,
        "format_issue_samples": issue_samples,
        "standard_layout_recognized": record_count > 0 and format_issue_count == 0,
        "format_check_scope": "Conservative 3I4,2F8,batch preflight until first terminator; not a complete Fortran reader or reflection/chemistry validation.",
        "sha256": sha256(path),
    }


def input_format_blockers(directives: dict[str, object], stats: dict[str, object]) -> list[str]:
    blockers = []
    try:
        kind = float(str(directives.get("HKLF", "")).split()[0])
    except (ValueError, IndexError):
        kind = 0
    if kind not in (3, 4, 5):
        blockers.append("This preflight supports external HKLF 3/4/5 only; other formats require review, not automatic conversion.")
    if not stats["standard_layout_recognized"]:
        blockers.append("HKL does not pass conservative three-index fixed-width inspection; inspect format_issue_samples before creating a job. Preserve possible satellite indices.")
    return blockers


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--stem", help="Select one basename when multiple pairs exist")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    directory = args.directory.expanduser().resolve()
    result: dict[str, object] = {
        "directory": str(directory),
        "exists": directory.is_dir(),
        "pairs": [],
        "unpaired": [],
        "warnings": [],
    }
    if not directory.is_dir():
        result["warnings"].append("Directory does not exist.")
    else:
        by_stem: dict[str, dict[str, Path]] = {}
        for path in directory.iterdir():
            if path.is_file() and path.suffix.lower() in {".hkl", ".ins"}:
                by_stem.setdefault(path.stem.casefold(), {})[path.suffix.lower()] = path

        selected = args.stem.casefold() if args.stem else None
        for key, files in sorted(by_stem.items()):
            if selected and key != selected:
                continue
            if ".hkl" not in files or ".ins" not in files:
                result["unpaired"].append(
                    {"stem": key, "files": [str(path) for path in files.values()]}
                )
                continue
            ins = files[".ins"]
            hkl = files[".hkl"]
            directives, warnings = parse_ins(ins)
            stats = reflection_stats(hkl)
            blockers = input_format_blockers(directives, stats)
            warnings.extend(blockers)
            pair = {
                "stem": ins.stem,
                "ins": {
                    "path": str(ins),
                    "size": ins.stat().st_size,
                    "sha256": sha256(ins),
                    "directives": directives,
                },
                "hkl": {"path": str(hkl), **stats},
                "warnings": warnings,
                "valid_for_processing": (
                    not (REQUIRED_INS - directives.keys())
                    and all(str(directives.get(card, "")).strip() for card in REQUIRED_INS)
                    and ins.stat().st_size > 0
                    and hkl.stat().st_size > 0
                    and not blockers
                ),
            }
            result["pairs"].append(pair)

        if args.stem and not result["pairs"]:
            result["warnings"].append(f"No complete pair found for stem: {args.stem}")
        elif not result["pairs"]:
            result["warnings"].append("No same-stem .hkl/.ins pair found.")
        elif len(result["pairs"]) > 1 and not args.stem:
            result["warnings"].append("Multiple input pairs found; select one with --stem.")

    ready = bool(result["pairs"]) and not (
        len(result["pairs"]) > 1 and not args.stem
    ) and all(pair["valid_for_processing"] for pair in result["pairs"])
    result["ready"] = ready

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Directory: {directory}")
        for pair in result["pairs"]:
            print(f"- {pair['stem']}: {pair['ins']['path']} + {pair['hkl']['path']}")
        for warning in result["warnings"]:
            print(f"WARNING: {warning}")
        print(f"Ready: {ready}")
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
