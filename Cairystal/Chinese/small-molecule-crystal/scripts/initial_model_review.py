"""Read-only post-solution screening; never certifies or relabels a structure.

Uses only the explicitly selected current candidate's paired CIF/RES and optional
LST/CHK. Geometric contacts and ADP outliers are hypotheses, not bond orders.
"""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics
import time
import gemmi
from structure_diagnostics import analyse, structure

LIGHT = {'C', 'N', 'O'}

def canonical_elements(values):
    result = []
    for value in values:
        name = str(value).strip().capitalize()
        if not name.isalpha() or gemmi.Element(name).atomic_number <= 0:
            raise ValueError('Invalid allowed element: ' + str(value))
        if name not in result:
            result.append(name)
    if not result:
        raise ValueError('An explicit allowed-element list is required; it is not a formula.')
    return result

def build_review(packet, allowed_elements):
    """Pure evidence triage; screening thresholds are explicitly not IUCr limits."""
    allowed = canonical_elements(allowed_elements)
    atoms = packet['all_atoms']
    sites = []
    findings = []
    for atom in atoms:
        if atom['element'] not in allowed:
            findings.append({'code': 'element_outside_input', 'atom': atom['label'],
                             'element': atom['element'], 'route': 'light_atoms'})
        if atom.get('res_context_status') != 'matched':
            findings.append({'code': 'cif_res_pairing_unresolved', 'atom': atom['label'], 'route': 'pairing'})
        if atom.get('non_positive_definite'):
            findings.append({'code': 'non_positive_ADP', 'atom': atom['label'], 'route': 'adp_shape'})
    for atom in packet['regions']:
        if atom['element'] not in LIGHT:
            continue
        candidates = [n for n in atom['neighbors'] if n['part_compatible'] is True
                      and n['within_covalent_radius_screen'] and n['element'] not in {'H', 'D'}
                      and not gemmi.Element(n['element']).is_metal]
        # Separate alternatives/partial sites; never treat nearby PARTs as bonds.
        neighbors = list({(n['label'], n['symmetry'], tuple(n['translation'])): n for n in candidates}.values())
        comparable = [n for n in neighbors if n['element'] in LIGHT and n.get('Ueq') is not None
                      and n['Ueq'] > 0 and n.get('occupancy') is not None
                      and atom.get('occupancy') is not None
                      and abs(n['occupancy'] - atom['occupancy']) <= .05]
        ref_u = statistics.median(n['Ueq'] for n in comparable) if len(comparable) >= 2 else None
        u = atom.get('Ueq')
        ratio = u / ref_u if ref_u and u is not None and u > 0 else None
        flags = []
        if u is None:
            flags.append('missing_Ueq')
        elif u <= 0:
            flags.append('non_positive_Ueq')
        if ratio is not None and ratio < .5:
            flags.append('low_relative_Ueq')
        if ratio is not None and ratio > 2.5:
            flags.append('high_relative_Ueq')
        if (atom.get('principal_rms_axis_ratio') or 0) > 4:
            flags.append('elongated_ADP')
        if atom.get('non_positive_definite'):
            flags.append('non_positive_ADP')
        if not neighbors:
            flags.append('isolated_site_check_symmetry_coordination_or_solvent')
        if len(neighbors) > {'C': 4, 'N': 4, 'O': 2}[atom['element']]:
            flags.append('too_many_close_nonmetal_contacts_review_connectivity')
        short = [n for n in neighbors if n['element'] in LIGHT and n['distance'] <
                 .72 * (gemmi.Element(atom['element']).covalent_r + gemmi.Element(n['element']).covalent_r)]
        if short:
            flags.append('very_short_contact')
        if flags:
            findings.append({'code': 'light_atom_review', 'atom': atom['label'], 'reasons': flags,
                             'route': 'light_atoms'})
        sites.append({'label': atom['label'], 'scattering_element': atom['element'],
                      'part': atom['part'], 'occupancy': atom['occupancy'], 'Ueq': u,
                      'neighbor_median_Ueq': ref_u, 'relative_Ueq': ratio,
                      'comparable_neighbor_count': len(comparable),
                      'geometric_contacts': neighbors, 'flags': flags,
                      'nearby_reported_Q_peaks': atom.get('nearby_reported_Q_peaks', []),
                      'candidate_elements_to_review': [e for e in allowed if e in LIGHT] if flags else [],
                      'assigned_bond_orders': None, 'assigned_charge': None,
                      'element_replacement_decided': False})
    accounting = packet.get('occupancy_audit') or {}
    return {'schema': 1, 'status': 'needs_review' if findings else 'screened_requires_chemical_review',
            'stage': '02_post_solution', 'allowed_elements': allowed, 'source_hashes': packet['source_hashes'],
            'source_directory': packet['source_directory'], 'space_group': packet['space_group'],
            'metrics': packet.get('gate', {}).get('metrics', {}),
            'difference_density_global_only': packet.get('difference_density'),
            'local_negative_density': None, 'sites': sites, 'findings': findings,
            'occupancy_warnings': accounting.get('warnings', []),
            'AB_alerts': packet.get('AB_alerts', []),
            'screening_thresholds': {'relative_Ueq_low': .5, 'relative_Ueq_high': 2.5,
                                     'minimum_comparable_neighbors': 2, 'occupancy_tolerance': .05,
                                     'rms_axis_ratio': 4, 'short_contact_covalent_radius_factor': .72},
            'next_actions': ['Check complete connectivity, valence, charge and symmetry.',
                             'Compare supported C/N/O assignments on identical observations and starting weights.',
                             'Inspect site-specific signed density; a truncated Q list cannot replace this.',
                             'Only after type/protonation review generate H and update UNIT/formula.'],
            'automatic_model_edit': False, 'scientific_acceptance': False,
            'limitations': ['Screening limits are triage hints, not PLATON alert definitions or acceptance limits.',
                           'Low U can indicate a too-light assignment; high U a too-heavy assignment, but occupancy, disorder and terminal motion can produce the same signs.',
                           'Distances are contacts, not proven bonds; bond orders/hybridization and protonation remain unknown.',
                           'Only nearest periodic images are used; small cells or unusual coordination need dedicated review.',
                           'No flag does not establish a correct structure or unique C/N/O assignment.']}

def review(directory, stem, allowed_elements):
    start = time.perf_counter()
    directory = Path(directory)
    if not stem or Path(stem).name != stem or any(c in stem for c in '/\\:'):
        raise ValueError('Use a basename stem, not a path.')
    for suffix in ['cif', 'res']:
        if not (directory / (stem + '.' + suffix)).is_file():
            raise ValueError('Initial review needs the current candidate CIF and RES; first run a short SHELXL baseline to produce paired files. Missing ' + suffix)
    parsed = structure(directory / (stem + '.cif'), directory / (stem + '.res'))
    _, cell, ops, atoms, _ = parsed
    focus = [a['label'] for a in atoms if a['element'] in LIGHT]
    packet = analyse(directory, stem, focus, 'provisional_initial_model', _parsed=parsed)
    result = build_review(packet, allowed_elements)
    # Useful geometry, still no automatic hybridization/element inference.
    lookup = {a['label']: a for a in atoms}
    for site in result['sites']:
        vectors = []
        origin = lookup[site['label']]['xyz']
        for neighbor in site['geometric_contacts'][:8]:
            target = gemmi.Op(neighbor['symmetry']).apply_to_xyz(lookup[neighbor['label']]['xyz'])
            v = cell.orthogonalize(gemmi.Fractional(*[target[i] + neighbor['translation'][i] - origin[i] for i in range(3)]))
            vectors.append((neighbor['label'], [v.x, v.y, v.z]))
        angles = []
        for (a, v), (b, w) in itertools.combinations(vectors, 2):
            norm = math.sqrt(sum(x*x for x in v) * sum(x*x for x in w))
            if norm > 0:
                angles.append({'neighbors': [a, b], 'angle_deg': round(math.degrees(math.acos(max(-1, min(1, sum(x*y for x,y in zip(v,w))/norm)))), 2)})
        site['contact_angles_not_bond_orders'] = angles
    result['stem'] = stem
    result['elapsed_s'] = round(time.perf_counter() - start, 4)
    from initial_decisions import decision_queue
    result['decision_queue'] = decision_queue(result)
    return result

def save_review(directory, stem, elements, output):
    """Always retain a diagnostic failure, never substitute a successful review."""
    output = Path(output)
    if output.exists():
        raise FileExistsError(str(output))
    try:
        result = review(directory, stem, elements)
    except (ValueError, OSError, RuntimeError, KeyError, TypeError) as exc:
        result = {'schema': 1, 'status': 'review_unavailable', 'stage': '02_post_solution',
                  'error': str(exc), 'source_directory': str(directory), 'scientific_acceptance': False,
                  'automatic_model_edit': False, 'next_actions': ['Resolve the diagnostic/input limitation; do not mark the initial model checked.']}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
    return {'status': result['status'], 'path': str(output),
            'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
            'finding_count': len(result.get('findings', [])), 'scientific_acceptance': False}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory', required=True, type=Path)
    p.add_argument('--stem', default='model')
    p.add_argument('--elements', nargs='+', required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--trial-output', type=Path, help='Optional NEW directory for bounded C/N/O contrasts; requires a complete paired bundle')
    p.add_argument('--profile', type=Path)
    p.add_argument('--max-sites', type=int, default=2)
    p.add_argument('--max-trials', type=int, default=4)
    p.add_argument('--run-trials', action='store_true', help='Run prepared baseline/contrasts and local validation; never adopt a model or upload')
    a = p.parse_args()
    if a.trial_output and not a.profile:
        p.error('--trial-output requires --profile')
    if a.run_trials and not a.trial_output:
        p.error('--run-trials requires --trial-output')
    result = save_review(a.directory, a.stem, a.elements, a.output)
    if a.trial_output and result['status'] != 'review_unavailable':
        from initial_decisions import prepare_element_trials
        from crystal_runtime import write_json
        reviewed=json.loads(a.output.read_text('utf-8'))
        result['element_trials']=prepare_element_trials(a.directory,a.stem,reviewed,a.trial_output,a.profile,a.max_sites,a.max_trials)
        if a.run_trials and result['element_trials']['status']=='prepared':
            from candidate_trials import run_plan
            from compare_diagnostic_trials import compare
            trials=run_plan(result['element_trials']['plan'])
            comparisons=[compare(trials[0],t) for t in trials[1:]] if trials and trials[0]['status']=='completed' else []
            write_json(a.trial_output/'comparison.json',{'results':trials,'comparisons':comparisons,
                'model_adopted':False,'next_action':'Review chemistry, density, H and charge before selecting; do not choose by R/AB alone.'})
            result['element_trials']['comparison']=str(a.trial_output/'comparison.json')
    print(json.dumps(result, ensure_ascii=False))
    return 2 if result['status'] == 'review_unavailable' else 0

if __name__ == '__main__':
    raise SystemExit(main())
