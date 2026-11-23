"""Infer a trial primitive Laue seed from measured HKLF 4 pairs in their original setting."""
import hashlib
import math
import statistics
from pathlib import Path

import gemmi

from ortho_laue import MAX_RPAIR, MIN_CC, MIN_PAIRS


def read_general(path):
    sums = {}
    fingerprint = hashlib.sha256()
    ended = False
    with Path(path).open("rb") as stream:
        for number, raw in enumerate(stream, 1):
            fingerprint.update(raw)
            if ended or not raw.strip():
                continue
            try:
                idx = tuple(int(raw[i:i+4]) for i in (0, 4, 8))
                if idx == (0, 0, 0):
                    ended = True
                    continue
                intensity, sigma = float(raw[12:20]), float(raw[20:28])
                batch = raw[28:].strip()
                if (batch and int(batch) < 0) or not all(map(math.isfinite, (intensity,sigma))):
                    raise ValueError()
            except ValueError as error:
                raise ValueError(f"Expected HKLF 4 at reflection line {number}") from error
            if not all(idx) or sigma <= 0:
                continue
            weight = 1 / sigma**2
            pair = sums.setdefault(idx, [0., 0.])
            pair[0] += intensity * weight
            pair[1] += weight
    data = {idx: (total / w, 1 / math.sqrt(w)) for idx, (total,w) in sums.items()}
    return data, fingerprint.hexdigest()


def test_rotation(op, data):
    pairs = []
    for idx, (a, sa) in data.items():
        mate = tuple(op.apply_to_hkl(idx))
        if idx >= mate or mate not in data:
            continue
        b, sb = data[mate]
        if a + b >= 4 * math.hypot(sa, sb):
            pairs.append((a, b))
    cc = residual = None
    if len(pairs) >= MIN_PAIRS:
        left, right = zip(*pairs)
        if min(left) != max(left) and min(right) != max(right):
            cc = statistics.correlation(left, right)
            residual = sum(abs(a-b) for a,b in pairs) / sum(abs(a)+abs(b) for a,b in pairs)
    decision = "inconclusive"
    if cc is not None:
        if cc >= MIN_CC and residual <= MAX_RPAIR:
            decision = "supported"
        elif cc < 0.80 or residual > 0.20:
            decision = "unsupported"
    return {"rotation":op.triplet(), "pairs":len(pairs), "cc":cc, "r_pair":residual, "decision":decision}


def infer(meta, path):
    if path is None:
        raise ValueError("A missing BRAVAIS declaration requires measured HKLF 4 intensities.")
    data, digest = read_general(path)
    # Strong general reflections in each nominally forbidden class contradict
    # conventional centring. F is a subset of A/B/C allowed reflections.
    strong = [idx for idx,(value,sigma) in data.items() if value > 5*sigma]
    parity = [((k+l)%2, (h+l)%2, (h+k)%2, (h+k+l)%2,
               (-h+k+l)%3 != 0, (h-k+l)%3 != 0) for h,k,l in strong]
    names = ("A","B","C","I","R_obverse","R_reverse")
    violations = dict(zip(names, map(sum, zip(*parity)))) if parity else dict.fromkeys(names, 0)
    evidence = {"hkl_sha256":digest, "strong_general_indices":len(strong),
                "centring_violations":violations, "operations":[], "passed":False,
                "source":"No BRAVAIS record; direct rotation mates, Friedel pairs kept separate."}
    meta["laue_screen"] = evidence
    if min(violations.values()) < max(MIN_PAIRS, .10 * len(strong)):
        raise ValueError("Centring unresolved. Inspect systematic absences or try alternative indexed seeds with the current HKL.")
    cell = gemmi.UnitCell(*meta["cell"])
    metric = gemmi.find_lattice_symmetry(cell, "P", 0.5)
    supported = [gemmi.Op("x,y,z")]
    for op in metric.sym_ops:
        if op.triplet() == "x,y,z" or op.det_rot() <= 0:
            continue
        result = test_rotation(op, data)
        evidence["operations"].append(result)
        if result["decision"] == "supported":
            supported.append(op)
    if any(r["decision"] == "inconclusive" for r in evidence["operations"]):
        raise ValueError("Rotation evidence is incomplete or borderline. Compare alternative Laue seeds using the current data.")
    ops = gemmi.GroupOps(supported)
    ops.add_missing_elements()
    if len(ops) != len(supported):
        raise ValueError("Supported intensity rotations do not form a group. Review competing symmetry candidates.")
    ops.add_inversion()
    group = gemmi.find_spacegroup_by_ops(ops)
    declared = set(meta.get("declared_symmetry", ()))
    if declared and (group is None or declared != {group.laue_str()}):
        raise ValueError("Declared SYMM conflicts with the measured trial seed. Review indexing.")
    symbol = group.xhm() if group else "non-standard primitive setting"
    evidence.update(passed=True, laue_hypothesis=symbol, metric_tolerance_degrees=.5,
                    minimum_rotation_pairs=MIN_PAIRS, minimum_cc=MIN_CC, maximum_r_pair=MAX_RPAIR)
    return 1, [op.triplet().upper() for op in supported[1:]], (
        f"Measured primitive Laue search seed {symbol}; verify space group, systematic absences and absolute structure independently.")
