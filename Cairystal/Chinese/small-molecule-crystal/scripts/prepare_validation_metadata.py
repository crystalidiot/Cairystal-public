"""Merge missing experimental scalars into a NEW CIF, preserving model/data tokens.

Requires Gemmi. Pairing must be established independently and recorded in the
supplied evidence file: matching cells alone never establish specimen identity.
No network, refinement, reference coordinates, calculated mu or report claims.
"""
import argparse
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path

import gemmi

TAGS = tuple('''
_cell_measurement_reflns_used _cell_measurement_theta_min
_cell_measurement_theta_max _cell_measurement_temperature
_exptl_crystal_description _exptl_crystal_colour
_exptl_crystal_size_min _exptl_crystal_size_mid _exptl_crystal_size_max
_exptl_crystal_density_meas _exptl_crystal_density_method
_exptl_absorpt_correction_type _exptl_absorpt_correction_T_min
_exptl_absorpt_correction_T_max _exptl_absorpt_process_details
_exptl_transmission_factor_min _exptl_transmission_factor_max
_diffrn_ambient_temperature _diffrn_radiation_wavelength
_diffrn_radiation_type _diffrn_radiation_probe _diffrn_radiation_monochromator
_diffrn_source _diffrn_source_type _diffrn_source_target
_diffrn_source_voltage _diffrn_source_current _diffrn_source_power
_diffrn_measurement_device _diffrn_measurement_device_type
_diffrn_measurement_method _diffrn_detector _diffrn_detector_type
_diffrn_detector_area_resol_mean
_computing_data_collection _computing_cell_refinement _computing_data_reduction
'''.split())
ESSENTIAL = TAGS[:3] + ('_exptl_crystal_description',)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def block_for(doc, name=None):
    candidates = [b for b in doc if b.find_value('_cell_length_a')]
    if name is not None:
        candidates = [b for b in candidates if b.name == name]
    if len(candidates) != 1:
        raise ValueError('Select exactly one structural CIF block; found ' + str(len(candidates)))
    return candidates[0]


def missing(token):
    # CIF dot means not applicable, not permission to fill it.
    return token is None or token == '?' or gemmi.cif.as_string(token).strip() == ''


def available(token):
    return token != '.' and not missing(token)


def equivalent(a, b):
    if a == b:
        return True
    # Treat spelling/spacing of Mo K-alpha etc. as serialization differences.
    return ''.join(gemmi.cif.as_string(a).lower().split()) == ''.join(gemmi.cif.as_string(b).lower().split())


def snapshot(doc):
    """All CIF data, including every loop and embedded multiline input."""
    out = {}
    for b in doc:
        fields = {}
        for item in b:
            if item.pair:
                k, v = item.pair
                fields[k.lower()] = ('scalar', v.replace('\r\n', '\n'))
            elif item.loop:
                loop = item.loop
                n = len(loop.tags)
                for i, tag in enumerate(loop.tags):
                    fields[tag.lower()] = ('loop', tuple(v.replace('\r\n', '\n') for v in loop.values[i::n]))
            elif item.frame:
                raise ValueError('Save frames require a separate reviewed route')
        out[b.name] = fields
    return out


def require_identity(source, target):
    checks = {}
    for tag in ('_cell_length_a', '_cell_length_b', '_cell_length_c',
                '_cell_angle_alpha', '_cell_angle_beta', '_cell_angle_gamma',
                '_diffrn_radiation_wavelength'):
        a, b = source.find_value(tag), target.find_value(tag)
        if not available(a) or not available(b):
            raise ValueError('Identity gate lacks ' + tag)
        av, bv = gemmi.cif.as_number(a), gemmi.cif.as_number(b)
        def su(token):
            match = re.fullmatch(r'([+-]?[0-9]+(?:\.[0-9]*)?)(?:\(([0-9]+)\))?([eE][+-]?[0-9]+)?', token)
            if not match or not match[2]: return 0.0
            decimals = len(match[1].split('.')[1]) if '.' in match[1] else 0
            exponent = int(match[3][1:]) if match[3] else 0
            return int(match[2]) * 10.0 ** (exponent-decimals)
        # SHELX headers can carry fewer significant figures than deposited CIFs.
        # This is an additional consistency gate, NEVER specimen identity proof.
        tolerance = max(1e-5, abs(av)*1e-6, 3*math.hypot(su(a), su(b)))
        if not math.isfinite(av + bv) or abs(av-bv) > tolerance:
            raise ValueError('Cell/setting/wavelength mismatch: ' + tag)
        checks[tag] = {'source': a, 'candidate': b, 'absolute_tolerance': tolerance,
                       'numeric_difference': abs(av-bv)}
    return checks


def prepare(source, candidate, output, pairing_evidence, source_block=None):
    source, candidate, output, pairing_evidence = map(Path, (source, candidate, output, pairing_evidence))
    if output.exists():
        raise FileExistsError('Never overwrite a CIF: ' + str(output))
    if not pairing_evidence.is_file():
        raise ValueError('Provide the independently reviewed input/reflection lineage record')
    audit_path = output.with_suffix('.metadata.json')
    if audit_path.exists():
        raise FileExistsError(str(audit_path))
    hashes = {str(p.resolve()): sha(p) for p in (source, candidate, pairing_evidence)}
    src_doc = gemmi.cif.read_file(str(source))
    doc = gemmi.cif.read_file(str(candidate))
    src, dst = block_for(src_doc, source_block), block_for(doc)
    identity = require_identity(src, dst)
    before = snapshot(doc)
    filled, conflicts, unknown, not_applicable = [], [], [], []
    for tag in TAGS:
        if src.find_loop(tag) or dst.find_loop(tag):
            raise ValueError('Metadata loop requires manual handling: ' + tag)
        new, old = src.find_value(tag), dst.find_value(tag)
        if old == '.':
            not_applicable.append(tag)
            continue
        if missing(old):
            if available(new):
                dst.set_pair(tag, new)
                filled.append({'tag': tag, 'before': old, 'after': new,
                               'source_block': src.name, 'source_locator': 'data_' + src.name + '/' + tag})
            else:
                unknown.append(tag)
        elif available(new) and not equivalent(old, new):
            conflicts.append({'tag': tag, 'candidate_retained': old, 'source': new})
    rendered = doc.as_string()
    parsed = gemmi.cif.read_string(rendered)
    after = snapshot(parsed)
    allowed_changes = {r['tag'].lower() for r in filled}
    expected = {k: dict(v) for k, v in before.items()}
    for r in filled:
        expected[dst.name][r['tag'].lower()] = ('scalar', r['after'].replace('\r\n', '\n'))
    if after != expected:
        raise ValueError('Unexpected CIF mutation outside approved experimental scalars')
    if not allowed_changes <= {t.lower() for t in TAGS}:
        raise ValueError('Nonexperimental tag change')
    for path, h in hashes.items():
        if sha(path) != h:
            raise ValueError('Input changed during merge: ' + path)
    record = {'created': datetime.now().astimezone().isoformat(),
              'source': str(source.resolve()), 'source_block': src.name,
              'candidate': str(candidate.resolve()), 'output': str(output.resolve()),
              'input_hashes': hashes, 'pairing_evidence': str(pairing_evidence.resolve()),
              'pairing_note': 'Lineage must be established by caller; cell/wavelength is an additional gate, not proof.',
              'identity_checks': identity, 'filled': filled, 'conflicts_retained': conflicts,
              'missing_in_both': unknown, 'not_applicable_retained': not_applicable,
              'essential_missing': [t for t in ESSENTIAL if not available(dst.find_value(t))],
              'all_other_CIF_data_unchanged': True, 'serialization_note': 'Whitespace and CRLF/LF may normalize; all other values and embedded input text are checked.', 'scientific_acceptance': False,
              'excluded': 'Reference atom/ADP/geometry/refinement/formula/mu/density-calculated/FCF, collection and refinement reflection statistics',
              'source_validation': 'Inherited collection record, not independently verified measurement'}
    with output.open('x', encoding='utf8', newline='\n') as f:
        f.write(rendered)
    record['output_sha256'] = sha(output)
    with audit_path.open('x', encoding='utf8') as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return record


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True)
    p.add_argument('--candidate', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--pairing-evidence', required=True)
    p.add_argument('--source-block')
    a = p.parse_args()
    r = prepare(a.source, a.candidate, a.output, a.pairing_evidence, a.source_block)
    print(json.dumps({'filled': len(r['filled']), 'conflicts': r['conflicts_retained'],
                      'essential_missing': r['essential_missing'], 'output': r['output']}, ensure_ascii=False))
