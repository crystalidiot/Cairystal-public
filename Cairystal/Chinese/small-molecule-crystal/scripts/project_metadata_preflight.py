"""Inspect explicitly permitted project metadata and HKL lineage, without merging.

Only the selected project root and its immediate olex2 directory are inventoried.
No reference CIF/RES/INS, model identity, arbitrary subdirectory or external include
is opened. This tool is not permission to read forbidden blind-test side files.
"""
import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re

from pipeline_intake import unlinked
from inspect_experiment_metadata import inspect_metadata

META_SUFFIXES = {".metacif", ".phil", ".pcf", ".cif_od"}
RAW_SUFFIXES = {".p4p", "._ls", ".raw", ".abs"}
MAX_ENTRIES = 2048
MAX_RAW_BYTES = 128 * 1024 * 1024


def inventory(project_dir, stem):
    """Names only; a name match is a candidate, never pairing evidence."""
    root = unlinked(project_dir)
    if not root.is_dir():
        raise ValueError("Project directory missing")
    if not stem or Path(stem).name != stem or any(c in stem for c in "/\\"):
        raise ValueError("Stem must be a basename")
    bases = {stem.casefold(), re.sub(r"_\d+m$", "", stem, flags=re.I).casefold()}
    found, skipped, dirs = [], [], [root]
    olex = root / "olex2"
    if olex.exists():
        try:
            unlinked(olex)
            if olex.is_dir():
                dirs.append(olex)
        except ValueError:
            skipped.append({"path": str(olex), "reason": "linked_directory_not_followed"})
    for directory in dirs:
        for number, p in enumerate(directory.iterdir(), 1):
            if number > MAX_ENTRIES:
                raise ValueError("Project inventory exceeds bounded entry limit")
            if not (p.suffix.lower() in META_SUFFIXES or p.name.lower() == "cif_od"):
                continue
            if p.name.lower() != "cif_od" and p.stem.casefold() not in bases:
                continue
            try:
                unlinked(p)
                if not p.is_file():
                    continue
            except ValueError:
                skipped.append({"path": str(p), "reason": "linked_file_not_followed"})
                continue
            found.append({"path": str(p), "pairing_status": "filename_candidate_only",
                          "content_read": False})
    return {"project_directory": str(root), "directories_listed": [str(p) for p in dirs],
            "candidates": sorted(found, key=lambda x: x["path"].casefold()),
            "skipped": skipped, "recursive": False}


def bounded_bytes(path):
    path = unlinked(path)
    if not path.is_file():
        raise ValueError("Explicit input file missing")
    with path.open("rb") as f:
        raw = f.read(MAX_RAW_BYTES + 1)
    if len(raw) > MAX_RAW_BYTES:
        raise ValueError("Raw input exceeds the 128 MiB limit")
    return raw


def fingerprint(path, hkl=False):
    raw = bounded_bytes(path)
    result = {"path": str(unlinked(path)), "sha256": hashlib.sha256(raw).hexdigest(),
              "bytes": len(raw)}
    if not hkl:
        return result
    result.update(reflection_count=None, numeric_rows_sha256=None,
                  numeric_comparison_scope="HKLF4 fixed-column rows, including batch; row order ignored")
    rows = []
    try:
        for line in raw.decode("ascii").splitlines():
            if not line.strip():
                continue
            indices = [int(line[i:i+4]) for i in (0, 4, 8)]
            if indices == [0, 0, 0]:
                break
            intensity, sigma = (Decimal(line[a:b].strip()) for a, b in ((12, 20), (20, 28)))
            if not intensity.is_finite() or not sigma.is_finite():
                raise ValueError("Non-finite HKL number")
            batch = line[28:].strip()
            # Preserve uncertainty about unsupported multi-column/extended rows.
            if batch and not re.fullmatch(r"[+-]?\d+", batch):
                raise ValueError("Unsupported extended HKL columns")
            rows.append(" ".join(map(str, indices)) + " " + str(intensity.normalize()) +
                        " " + str(sigma.normalize()) + " " + (str(int(batch)) if batch else ""))
        if not rows:
            raise ValueError("No reflections")
        result.update(reflection_count=len(rows), numeric_rows_sha256=hashlib.sha256(
            "\n".join(sorted(rows)).encode("ascii")).hexdigest())
    except (UnicodeError, ValueError, InvalidOperation):
        result["numeric_comparison_issue"] = "Unsupported HKL layout; no numeric equivalence claimed"
    return result


def compare_files(first, second, hkl=False):
    a, b = fingerprint(first, hkl), fingerprint(second, hkl)
    same = a["sha256"] == b["sha256"]
    numeric = (a["numeric_rows_sha256"] == b["numeric_rows_sha256"]
               if hkl and a["numeric_rows_sha256"] and b["numeric_rows_sha256"] else None)
    return {"input": a, "project": b, "hash_equal": same, "numeric_equal": numeric,
            "status": "identical_bytes" if same else "different_bytes",
            "same_experiment_confirmed": False,
            "interpretation": "Matching raw companions can support provenance review; they do not prove HKL equivalence."}


def unique_named(directory, name):
    choices = [p for p in directory.iterdir() if p.name.casefold() == name.casefold()]
    if len(choices) > 1:
        raise ValueError("Ambiguous case-insensitive source name")
    if not choices:
        return None
    return unlinked(choices[0])


def preflight(project_dir, hkl, sources=None, raw_companions=(), encoding="utf-8-sig"):
    root, hkl = unlinked(project_dir), unlinked(hkl)
    inv = inventory(root, hkl.stem)
    chosen = [Path(item["path"]) for item in inv["candidates"]] if sources is None else list(map(Path, sources))
    reports, errors, hashes, observations, links = [], [], {}, {}, []
    hkl_record = fingerprint(hkl, True)
    hashes[str(hkl)] = hkl_record["sha256"]
    project_hkl = unique_named(root, hkl.name)
    if project_hkl is not None:
        comparison = compare_files(hkl, project_hkl, True)
        links.append({"kind": "hkl", **comparison})
        hashes[str(project_hkl)] = comparison["project"]["sha256"]

    def observe(tag, item):
        observations.setdefault(tag, []).append(item)

    for candidate in chosen:
        p = unlinked(candidate)
        if p.parent not in {root, root / "olex2"}:
            raise ValueError("Metadata source is outside the explicit bounded project")
        if p.suffix.lower() not in META_SUFFIXES and p.name.lower() != "cif_od":
            raise ValueError("Only metacif/phil/pcf/cif_od sources supported in project inspection")
        digest = fingerprint(p)["sha256"]
        hashes[str(p)] = digest
        try:
            report = inspect_metadata(p, encoding)
            reports.append(report)
            if report["source_sha256"] != digest:
                raise ValueError("Metadata source changed during inspection")
            for block in report["blocks"]:
                for tag, value in block["fields"].items():
                    observe(tag, {"source": str(p), "source_sha256": digest,
                                  "block": block["block"], **value})
        except (ValueError, OSError, RuntimeError) as exc:
            errors.append({"source": str(p), "stage": "metadata_read", "reason": str(exc)})

    for raw_path in raw_companions:
        raw_path = unlinked(raw_path)
        if raw_path.suffix.lower() not in RAW_SUFFIXES:
            raise ValueError("Unsupported raw-companion type")
        item = fingerprint(raw_path)
        hashes[str(raw_path)] = item["sha256"]
        peer = unique_named(root, raw_path.name)
        if peer is not None:
            comparison = compare_files(raw_path, peer)
            links.append({"kind": "raw_companion", **comparison})
            hashes[str(peer)] = comparison["project"]["sha256"]
        if raw_path.suffix.lower() == ".p4p":
            from p4p_metadata import read_p4p
            try:
                content = bounded_bytes(raw_path).decode("latin1")
                meta = read_p4p(content, require_core=False)
                # The P4P temperature scope is deliberately unconfirmed here.
                if "temperature_K" in meta:
                    line = next((n for n, s in enumerate(content.splitlines(), 1)
                                 if s.lstrip().upper().startswith("CSIZE ")), None)
                    observe("p4p_temperature_scope_unconfirmed", {
                        "source": str(raw_path), "source_sha256": item["sha256"],
                        "source_line": line, "token": str(meta["temperature_K"]),
                        "value": str(meta["temperature_K"]), "state": "present_unverified",
                        "unit": "K", "temperature_evidence": meta["temperature_evidence"]})
            except (ValueError, OSError, RuntimeError) as exc:
                errors.append({"source": str(raw_path), "stage": "p4p_read", "reason": str(exc)})

    conflicts = []
    for tag, entries in observations.items():
        known = [x for x in entries if x["state"] == "present_unverified"]
        # Do not silently round temperatures or merge different device names.
        def signature(item):
            try:
                return ("number", Decimal(item["value"]))
            except InvalidOperation:
                return ("text", item["value"].strip().casefold())
        if len({signature(x) for x in known}) > 1:
            conflicts.append({"tag": tag, "reason": "different_recorded_values", "observations": known})
    p4p_temps = observations.get("p4p_temperature_scope_unconfirmed", [])
    for tag in ("_diffrn_ambient_temperature", "_cell_measurement_temperature"):
        for project in observations.get(tag, []):
            for raw in p4p_temps:
                try:
                    delta = Decimal(project["value"]) - Decimal(raw["value"])
                except InvalidOperation:
                    continue
                if delta:
                    conflicts.append({"tag": tag, "reason": "project_vs_raw_temperature_difference_scope_requires_review",
                                      "difference_K": str(delta), "observations": [project, raw]})
    unchanged = all(fingerprint(p)["sha256"] == digest for p, digest in hashes.items())
    if not unchanged:
        raise ValueError("Source changed during preflight")
    lineage_issues = [{"path": row["project"]["path"], "reason": "different_HKL_bytes",
                       "numeric_equal": row["numeric_equal"],
                       "same_reflection_count": row["input"]["reflection_count"] == row["project"]["reflection_count"]
                       if row["input"]["reflection_count"] is not None and row["project"]["reflection_count"] is not None else None}
                      for row in links if row["kind"] == "hkl" and not row["hash_equal"]]
    return {"schema": 1, "status": "needs_review" if conflicts or errors or lineage_issues else "inspected",
            "inventory": inv, "input_hkl": hkl_record, "source_reports": reports,
            "lineage_comparisons": links, "lineage_issues": lineage_issues,
            "observations": observations, "conflicts": conflicts,
            "errors": errors, "input_hashes": hashes, "inputs_unchanged": unchanged,
            "ready_for_merge": False, "same_experiment_confirmed": False, "ai_calls": 0,
            "missing_source_hint": "If needed, supply this specimen's Olex2 metacif/phil, PCF or cif_od project records; never borrow another specimen's values.",
            "limitations": ["No separate CIF/RES/INS model files opened. Whole permitted metadata files are read internally.",
                            "Pairing, units and conflicts require review before a separate frozen metadata-ledger import.",
                            "A project-record temperature does not prove the original measurement or precision.",
                            "Cell and diffraction temperature are distinct; raw P4P scope is not inferred."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--hkl", required=True)
    parser.add_argument("--source", action="append", help="Explicit allowed subset; default same-stem project companions")
    parser.add_argument("--raw-companion", action="append", default=[])
    parser.add_argument("--encoding", default="utf-8-sig")
    args = parser.parse_args()
    try:
        result = preflight(args.project_dir, args.hkl, args.source, args.raw_companion, args.encoding)
    except (ValueError, OSError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "ready_for_merge": False, "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
