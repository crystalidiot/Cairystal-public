"""Screen a declared primitive orthorhombic indexing against measured HKLF 4 intensities."""
import hashlib
import math
import statistics
from pathlib import Path


# Conservative routing thresholds, not universal crystallographic acceptance criteria.
MIN_PAIRS = 30
MIN_CC = 0.92
MAX_RPAIR = 0.12
ROTATIONS = ((1, -1, -1), (-1, 1, -1), (-1, -1, 1))


def screen(path):
    totals = {}
    digest = hashlib.sha256()
    ended = False
    with Path(path).open('rb') as stream:
        for line_number, raw in enumerate(stream, 1):
            digest.update(raw)
            if ended:
                continue
            if not raw.strip():
                ended = True
                continue
            try:
                hkl = tuple(int(raw[i:i+4]) for i in (0, 4, 8))
                if hkl == (0, 0, 0):
                    ended = True
                    continue
                intensity, sigma = float(raw[12:20]), float(raw[20:28])
                batch = raw[28:32].strip()
                if (batch and int(batch) < 0) or not all(map(math.isfinite, (intensity, sigma))):
                    raise ValueError()
            except ValueError as exc:
                raise ValueError(f'Invalid or unsupported HKLF 4 record at line {line_number}') from exc
            if not all(hkl) or sigma <= 0:
                continue
            weight = 1.0 / sigma**2
            values = totals.setdefault(hkl, [0., 0.])
            values[0] += weight * intensity
            values[1] += weight
    data = {k: (v/w, 1/math.sqrt(w)) for k, (v, w) in totals.items()}
    operations = []
    for signs in ROTATIONS:
        pairs = []
        for hkl, (a, sa) in data.items():
            mate = tuple(i*s for i, s in zip(hkl, signs))
            if hkl >= mate or mate not in data:
                continue
            b, sb = data[mate]
            if a+b >= 4 * math.hypot(sa, sb):
                pairs.append((a,b))
        cc = residual = None
        if len(pairs) >= MIN_PAIRS:
            left, right = zip(*pairs)
            denominator = sum(abs(a)+abs(b) for a,b in pairs)
            residual = sum(abs(a-b) for a,b in pairs)/denominator
            if max(left) != min(left) and max(right) != min(right):
                cc = statistics.correlation(left, right)
        passed = cc is not None and cc >= MIN_CC and residual <= MAX_RPAIR
        operations.append(dict(signs=signs, pairs=len(pairs), cc=cc, r_pair=residual, passed=passed))
    return dict(laue_hypothesis='mmm', passed=all(op['passed'] for op in operations),
                hkl_sha256=digest.hexdigest(), general_indices=len(data), operations=operations,
                minimum_pairs_per_operator=MIN_PAIRS, minimum_cc=MIN_CC, maximum_r_pair=MAX_RPAIR,
                sampling='General hkl, distinct same-index observations averaged by inverse variance; '
                         'direct rotation mates only, joint I/sigma >= 4. Friedel mates kept separate.')


class LaueReviewRequired(ValueError):
    def __init__(self, evidence):
        self.evidence = evidence
        details = ', '.join(f"{op['signs']} pairs={op['pairs']} CC={op['cc']} Rpair={op['r_pair']}"
                            for op in evidence['operations'] if not op['passed'])
        super().__init__('Orthorhombic P requires Laue review; inspect unmerged measurements or provide a reviewed INS. ' + details)
