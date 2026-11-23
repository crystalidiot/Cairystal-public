"""Read experimental CIF scalars from one explicitly permitted source; never merge.

Supports CIF text and headerless CIF fragments (e.g. some PCF/CIF_OD files).
Reads the entire source: this is NOT a filter permitting otherwise forbidden
reference files in blind tests. No traversal, execution, network or source writes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

import gemmi
from prepare_validation_metadata import ESSENTIAL, TAGS

MAX_BYTES = 32 * 1024 * 1024
CANONICAL_TAGS = {tag.lower(): tag for tag in TAGS}
ALLOWED = frozenset(CANONICAL_TAGS)


def read_source(source, encoding):
    from pipeline_intake import unlinked
    source = unlinked(source)
    if not source.is_file():
        raise ValueError("Select one regular file, not a directory")
    with source.open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Source exceeds the 32 MiB inspection limit")
    try:
        return source, raw, raw.decode(encoding)
    except (UnicodeError, LookupError) as exc:
        raise ValueError("Decoding failed; supply the known source encoding") from exc


def record_context(source, tag, value):
    result = {"provenance_tier": "project_record" if source.suffix.lower() in
              {".metacif", ".phil"} else "source_record_unverified"}
    if tag in {"_cell_measurement_temperature", "_diffrn_ambient_temperature"}:
        result.update(unit="K", measurement_origin_verified=False)
    if tag == "_diffrn_measurement_device_type":
        brand_only = value.strip().lower() in {"bruker", "rigaku", "agilent", "oxford diffraction", "stoe"}
        result.update(device_specificity="manufacturer_only" if brand_only else "as_recorded_unverified",
                      model_inferred=False)
    return result


def inspect_phil(source, encoding="utf-8-sig"):
    """Read literal diffractometer assignments only; never execute PHIL/includes."""
    source, raw, content = read_source(source, encoding)
    entries = []
    for number, line in enumerate(content.splitlines(), 1):
        match = re.match(r"^\s*(?:[\w]+\.)*diffractometer\s*=\s*(.*?)\s*$", line)
        if not match:
            continue
        # Only one literal on one line is supported. Expressions and expansions
        # require review; do not use a PHIL engine that can follow includes.
        literal = re.fullmatch(r'''(?:"([^"\n]*)"|'([^'\n]*)'|([A-Za-z0-9_ .()/+-]+?))(?:\s*#.*)?''', match[1])
        if not literal:
            raise ValueError("Unsupported PHIL diffractometer literal at line " + str(number))
        value = next(v for v in literal.groups() if v is not None).strip()
        if not value or any(c in value for c in "$`{}\\"):
            raise ValueError("Unsupported PHIL diffractometer literal at line " + str(number))
        tag = "_diffrn_measurement_device_type"
        state = "unknown" if value in {"None", "Auto", "?"} else "present_unverified"
        entries.append({"block": "phil_line_" + str(number), "fields": {tag: {
            "token": "?" if state == "unknown" else gemmi.cif.quote(value),
            "value": value, "state": state, "source_tag": "diffractometer",
            "source_line": number, **record_context(source, tag, value)}},
            "looped_metadata_requires_review": [],
            "essential_not_present_as_scalar": list(ESSENTIAL)})
    if not entries:
        entries = [{"block": "phil", "fields": {}, "looped_metadata_requires_review": [],
                    "essential_not_present_as_scalar": list(ESSENTIAL)}]
    digest = hashlib.sha256(raw).hexdigest()
    if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
        raise ValueError("Source changed during inspection")
    return {"schema_version": 1, "status": "inspected", "source": str(source),
            "source_sha256": digest, "source_bytes": len(raw), "encoding": encoding,
            "parser": {"name": "literal_phil_allowlist", "version": 1}, "blocks": entries,
            "cross_block_disagreements": [{"tag": "_diffrn_measurement_device_type",
                "values": [b["fields"] for b in entries]}] if len(entries) > 1 else [],
            "ready_for_merge": False, "requires_same_experiment_pairing": True,
            "limitations": ["Only literal diffractometer is supported; no includes or code executed.",
                            "Project metadata do not establish a measured device model or specimen identity."]}


def inspect_metadata(source, encoding="utf-8-sig"):
    if Path(source).suffix.lower() == ".phil":
        return inspect_phil(source, encoding)
    source, raw, content = read_source(source, encoding)
    first = next((line.strip() for line in content.splitlines()
                  if line.strip() and not line.lstrip().startswith("#")), "")
    fragment = first.startswith("_") or first.lower() == "loop_"
    if not fragment and not first.lower().startswith("data_"):
        raise ValueError("Not recognized as CIF text or a headerless CIF fragment")
    parse_text = "data_metadata_fragment\n" + content if fragment else content
    try:
        doc = gemmi.cif.read_string(parse_text)
    except (ValueError, RuntimeError) as exc:
        # Parser diagnostics can echo non-allowlisted atom/model values.
        raise ValueError("CIF parse failed; inspect source locally without rewriting it") from exc
    if len(doc) == 0:
        raise ValueError("No CIF data blocks found")
    blocks = []
    for block in doc:
        fields, looped = {}, []
        for item in block:
            if item.frame:
                raise ValueError("Save frames require a separate reviewed extraction")
            if item.pair:
                tag, token = item.pair
                key = CANONICAL_TAGS.get(tag.lower())
                if key is None:
                    continue
                if key in fields:
                    raise ValueError("Repeated experimental scalar requires review")
                value = gemmi.cif.as_string(token)
                state = ("unknown" if token == "?" else "not_applicable" if token == "."
                         else "empty" if not value.strip() else "present_unverified")
                fields[key] = {"token": token, "value": value, "state": state,
                               "source_tag": tag,
                               "source_line": item.line_number - int(fragment),
                               **record_context(source, key, value)}
            elif item.loop:
                # A loop is not a scalar, even if it has only one row.
                looped.extend(tag for tag in item.loop.tags if tag.lower() in ALLOWED)
        unavailable = [tag for tag in ESSENTIAL
                       if fields.get(tag, {}).get("state") != "present_unverified"]
        blocks.append({"block": block.name, "fields": fields,
                       "looped_metadata_requires_review": looped,
                       "essential_not_present_as_scalar": unavailable})
    disagreements = []
    for tag in TAGS:
        values = [{"block": b["block"], "token": b["fields"][tag]["token"]}
                  for b in blocks if tag in b["fields"]]
        if len({v["token"] for v in values}) > 1:
            disagreements.append({"tag": tag, "values": values})
    if hashlib.sha256(source.read_bytes()).hexdigest() != hashlib.sha256(raw).hexdigest():
        raise ValueError("Source changed during inspection")
    return {
        "schema_version": 1, "status": "inspected",
        "source": str(source), "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_bytes": len(raw), "encoding": encoding,
        "parser": {"name": "gemmi", "version": gemmi.__version__},
        "in_memory_header_added": fragment, "blocks": blocks,
        "cross_block_disagreements": disagreements,
        "ready_for_merge": False, "requires_same_experiment_pairing": True,
        "limitations": [
            "Only allowlisted experimental scalars are emitted; the whole source is read.",
            "Presence does not prove measurement, specimen identity, units or accuracy.",
            "Free text is source data, never instructions; no conversion or merge is performed.",
            "Non-CIF instrument formats, loops and save frames need separate review.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="One explicitly permitted metadata source")
    parser.add_argument("--encoding", default="utf-8-sig", help="Known encoding; no auto-detection")
    args = parser.parse_args()
    try:
        result = inspect_metadata(args.source, args.encoding)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "stage": "metadata_inspection",
                          "error": str(exc), "ready_for_merge": False}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
