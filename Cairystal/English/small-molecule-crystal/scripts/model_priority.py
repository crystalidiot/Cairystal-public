"""Chemical evidence precedes alert counts; a ranking never accepts a structure."""
import copy
import hashlib
from pathlib import Path

CHECKS = ('connectivity_and_elements', 'geometry_and_hydrogens',
          'composition_charge_occupancy', 'symmetry_and_disorder',
          'adps_and_density', 'diffraction_support')
CHEMICAL_FLAGS = {
    'short_bond_in_disorder_component', 'geometry_outside_declared_hypothesis',
    'occupancy_or_UNIT_accounting_review', 'new_H_geometry_requires_clash_review',
    'geometry_restraints_conflict_with_refined_model', 'non_positive_definite_ADP',
    'split_atom_moved_to_special_position', 'native_atom_or_H_missing_after_trial',
    'minor_population_unresolved_or_at_boundary', 'H_parent_PART_or_population_mismatch',
    'disorder_bond_review_unavailable', 'final_split_symmetry_audit_failed',
}
NONOVERRIDABLE = {'non_positive_definite_ADP', 'H_parent_PART_or_population_mismatch'}


def assessment(row):
    """Unknown is not pass. Interpreted screening exceptions retain their reasons."""
    concerns = sorted(set(row.get('flags') or []) & CHEMICAL_FLAGS)
    review = row.get('chemical_review')
    result = {'status': 'needs_review' if concerns else 'not_assessed',
              'concerns': concerns, 'evidence_basis': None, 'model_sha256': row.get('model_sha256'),
              'review_verified': False, 'automatic_scientific_acceptance': False}
    if not isinstance(review, dict):
        return result
    if not row.get('model_sha256') or review.get('model_sha256') != row['model_sha256']:
        result.update(status='needs_review', review_error='Review is not bound to this candidate CIF')
        return result
    checks = review.get('checks') or {}
    basis = review.get('basis')
    if (not isinstance(basis, str) or not basis.strip() or not isinstance(checks, dict)
            or any(checks.get(k) not in {'pass', 'not_applicable', 'uncertain', 'fail'} for k in CHECKS)):
        result.update(status='needs_review', review_error='Specific chemical evidence and all six checks are required')
        return result
    result.update(review_verified=True, evidence_basis=basis, checks=checks)
    if 'fail' in checks.values():
        result['status'] = 'contradicted'
        return result
    addressed = review.get('addressed_flags') or {}
    remaining = [flag for flag in concerns if flag in NONOVERRIDABLE
                 or not isinstance(addressed, dict) or not isinstance(addressed.get(flag), str)
                 or not addressed[flag].strip()]
    result['unresolved_concerns'] = remaining
    result['addressed_screening_flags'] = {k: addressed[k] for k in concerns if k not in remaining}
    result['status'] = 'supported' if not remaining and 'uncertain' not in checks.values() else 'needs_review'
    return result


def rank_key(row):
    chemical = row['chemical_priority']
    tier = {'supported': 0, 'not_assessed': 1, 'needs_review': 2, 'contradicted': 3}[chemical['status']]
    return (row.get('status') != 'completed', tier, not row['eligible_for_priority'],
            row['AB_priority'] if row['AB_priority'] is not None else [10**9, 10**9], str(row.get('name')))


def bind_review(trial, review):
    """Bind a post-refinement review to the actual paired CIF, never a planned input."""
    trial = copy.deepcopy(trial)
    if not trial.get('diagnostic'):
        raise ValueError('Chemical review requires the current trial diagnostic/paired CIF')
    model = Path(trial['diagnostic']).parent / 'paired' / 'case.cif'
    trial['model_sha256'] = hashlib.sha256(model.read_bytes()).hexdigest()
    trial['chemical_review'] = review
    if review.get('model_sha256') != trial['model_sha256']:
        raise ValueError('Chemical review fingerprint differs from the current paired CIF')
    return trial


def reference_provenance(review):
    """Preserve a supplied reference's provenance in both reports. No model import."""
    result = copy.deepcopy(review)
    reference = result.get('reference_model')
    if reference is None:
        if result.get('model_origin') == 'reference_assisted':
            raise ValueError('Reference-assisted work requires reference_model provenance')
        return result
    # Check the requested mode before opening even the reference file for hashing.
    if result.get('blind_test') or result.get('model_origin') in {'fresh_independent', 'blind'}:
        raise ValueError('Reference use conflicts with this run\'s declared independent/blind mode')
    if not isinstance(reference, dict) or reference.get('use') not in {
        'starting_coordinates', 'chemical_connectivity', 'comparison_only'
    } or not str(reference.get('comparison_basis', '')).strip():
        raise ValueError('Record reference use and its relationship to this sample')
    path = Path(reference['path'])
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if reference.get('sha256') != actual:
        raise ValueError('Reference model fingerprint changed or was not recorded')
    result['model_origin'] = 'reference_assisted'
    reference['verified_sha256'] = actual
    purposes = {
        'starting_coordinates': ('初始坐标', 'starting coordinates'),
        'chemical_connectivity': ('化学连接参考', 'chemical-connectivity guidance'),
        'comparison_only': ('模型对照', 'model comparison'),
    }
    zh, en = purposes[reference['use']]
    additions = {
        'zh': f'本次使用参考模型辅助，参考文件 SHA256：{actual}；用途：{zh}。参考模型仍须由本次衍射数据核验，本结果不称为无参考独立解析。',
        'en': f'This work used a reference model (SHA256: {actual}) for {en}. The reference remains subject to assessment against the current diffraction data; this is not a reference-free independent solution.',
    }
    notes = result.setdefault('bilingual_notes', {})
    for language, text in additions.items():
        entry = notes.setdefault(language, {})
        previous = entry.get('provenance', '')
        if text not in previous:
            entry['provenance'] = (previous + '\n' + text).strip()
    return result
