"""Reuse paired experiment records before asking questions; never search for models.

Consumes the existing metadata collector's ledger, whose input hashes and sample
association are checked again. Only intake observations are copied, not structure
coordinates, chemical identity or upload permission.
"""
import copy
import json
import math
from pathlib import Path

from crystal_runtime import regular, sha
from pipeline_intake import unlinked

FIELD_TAGS = {
    'colour': ['_exptl_crystal_colour'],
    'habit': ['_exptl_crystal_description'],
    'dimensions_mm': ['_exptl_crystal_size_min', '_exptl_crystal_size_mid', '_exptl_crystal_size_max'],
    'temperature': ['_diffrn_ambient_temperature'],
    'instrument': ['_diffrn_measurement_device_type'],
    'radiation': ['_diffrn_radiation_type'],
}
LABELS = {
    'colour': ('颜色', 'colour'), 'habit': ('形状', 'shape'),
    'dimensions_mm': ('三维尺寸（mm）', 'three dimensions (mm)'),
    'temperature': ('衍射温度', 'diffraction temperature'),
    'instrument': ('仪器型号', 'instrument model'), 'radiation': ('辐射源', 'radiation'),
}
UNKNOWN = {'', '?', '.', 'unknown', 'not known', 'not provided', '不清楚', '未知', '不知道'}


def present(value):
    if value is None or value == []:
        return False
    return not isinstance(value, str) or value.strip().casefold() not in UNKNOWN


def comparable(field, value):
    from intake_once import COLOURS, HABITS, dimensions
    if field == 'dimensions_mm':
        return sorted(dimensions(value) or [])
    if field == 'temperature':
        number = float(value['value'])
        return number + (273.15 if value.get('unit', 'K') == 'C' else 0)
    value = str(value).strip()
    value = (COLOURS if field == 'colour' else HABITS if field == 'habit' else {}).get(value, value)
    return ' '.join(value.casefold().replace('colorless', 'colourless').split())


def equal(field, a, b):
    a, b = comparable(field, a), comparable(field, b)
    if isinstance(a, (float, int)) and isinstance(b, (float, int)):
        return math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-9)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(math.isclose(x, y, rel_tol=1e-9, abs_tol=1e-9) for x, y in zip(a, b))
    return a == b


def read_ledger(path, data_dir=None, expected_hkl=None):
    import gemmi
    from experiment_metadata_state import validate
    from prepare_validation_metadata import available
    path = regular(unlinked(path))
    record = json.loads(path.read_text('utf-8-sig'))
    if record.get('schema') != 1 or not record.get('sources') or not record.get('input_hashes'):
        raise ValueError('Use metadata collect output with paired sources and input hashes')
    hkl = unlinked(record['hkl'])
    root = unlinked(data_dir) if data_dir else hkl.parent
    if root != hkl.parent:
        raise ValueError('Metadata ledger belongs to a different specimen directory')
    if expected_hkl:
        if unlinked(expected_hkl) != hkl:
            raise ValueError('Metadata ledger belongs to a different HKL')
    elif any(p.suffix.lower()=='.hkl' and p != hkl for p in root.iterdir()):
        raise ValueError('Multiple HKL files in specimen directory. Select the intended --hkl.')
    if record.get('hkl_sha256') != sha(regular(hkl)):
        raise ValueError('Metadata ledger HKL changed')
    for source, digest in record['input_hashes'].items():
        if sha(regular(unlinked(source))) != digest:
            raise ValueError('Metadata ledger input changed: ' + str(source))
    for source in record['sources']:
        if not source.get('basis') or record['input_hashes'].get(source['path']) != source.get('sha256'):
            raise ValueError('Metadata ledger source lacks paired provenance')
    allowed = {tag for tags in FIELD_TAGS.values() for tag in tags}
    fields = {tag: token for tag, token in record.get('resolved', {}).items()
              if tag in allowed and available(token) and present(gemmi.cif.as_string(token))}
    errors = validate(fields)
    if errors:
        raise ValueError('Invalid intake metadata: ' + json.dumps(errors, ensure_ascii=False))
    values, conflicts = {}, {}
    for field, tags in FIELD_TAGS.items():
        if any(tag in record.get('conflicts', {}) for tag in tags):
            conflicts[field] = {tag: record['conflicts'][tag] for tag in tags if tag in record['conflicts']}
            continue
        if not all(tag in fields for tag in tags):
            continue
        if field == 'dimensions_mm':
            values[field] = [gemmi.cif.as_number(fields[tag]) for tag in tags]
        elif field == 'temperature':
            values[field] = {'value': gemmi.cif.as_number(fields[tags[0]]), 'unit': 'K'}
        else:
            values[field] = gemmi.cif.as_string(fields[tags[0]])
    partial_sizes = {key: gemmi.cif.as_number(fields['_exptl_crystal_size_' + key])
                     for key in ('min', 'mid', 'max') if '_exptl_crystal_size_' + key in fields}
    return {'path': str(path), 'sha256': sha(path), 'data_dir': str(root), 'partial_sizes_mm': partial_sizes,
            'hkl':str(hkl), 'hkl_sha256':record['hkl_sha256'],
            'values': values, 'conflicts': conflicts, 'cif_tokens': fields,
            'provenance': {tag: record.get('observations', {}).get(tag, []) for tag in fields}}


def prepare(data, ledger=None, language='zh-CN', expected_hkl=None):
    """Produce prefill, a compact question plan, and a replayable source receipt."""
    data = copy.deepcopy(data)
    from intake_once import temperature_kelvin
    if 'temperature' in data and temperature_kelvin(data['temperature']) is None:
        data['temperature'] = None
    previous_asked = data.pop('_previous_asked_fields', []) or data.get('question_plan', {}).get('answered_unknown_fields', [])
    receipt = data.get('metadata_ledger')
    path = ledger or (receipt or {}).get('path')
    target = expected_hkl or (receipt or {}).get('hkl')
    metadata = read_ledger(path, data.get('data_dir'), target) if path else None
    if metadata and receipt and not ledger and receipt.get('sha256') != metadata['sha256']:
        raise ValueError('Metadata ledger changed since form generation; refresh its source check')
    conflicts, reused = {}, {}
    if metadata:
        data['data_dir'] = metadata['data_dir']
        data['metadata_ledger'] = {'path': metadata['path'], 'sha256': metadata['sha256']}
        if 'hkl' in metadata:
            data['metadata_ledger'].update(hkl=metadata['hkl'],hkl_sha256=metadata['hkl_sha256'])
        conflicts.update(metadata['conflicts'])
        for field, value in metadata['values'].items():
            if present(data.get(field)) and not equal(field, data[field], value):
                conflicts[field] = {'entered': data[field], 'file': value}
            else:
                data[field] = value
                reused[field] = value
        if present(data.get('dimensions_mm')) and metadata['partial_sizes_mm'] and 'dimensions_mm' not in conflicts:
            lengths = comparable('dimensions_mm', data['dimensions_mm'])
            if any(not math.isclose(lengths[i], metadata['partial_sizes_mm'][key], rel_tol=1e-9, abs_tol=1e-9)
                   for i, key in enumerate(('min', 'mid', 'max')) if key in metadata['partial_sizes_mm']):
                conflicts['dimensions_mm'] = {'entered': data['dimensions_mm'], 'file': metadata['partial_sizes_mm']}
    known = {field: data[field] for field in FIELD_TAGS if present(data.get(field)) and field not in conflicts}
    # Prior explicit unknown answers are not another invitation to ask again.
    answered_unknown = [field for field in previous_asked if not present(data.get(field))]
    missing = [field for field in ('colour', 'habit', 'dimensions_mm')
               if field not in known and field not in conflicts and field not in answered_unknown]
    label_index = 1 if language == 'en' else 0
    questions = []
    if missing:
        labels = ', '.join(LABELS[field][label_index] for field in missing)
        questions.append(('Please provide only the missing fields: ' if language == 'en' else '请只补充缺失项：') + labels)
        if len(missing) == 3:
            questions[0] += ('. Example: green, block, 0.050 × 0.051 × 0.052 mm. Enter unknown if needed.'
                             if language == 'en' else '。填写示例：绿色，块状，0.050 × 0.051 × 0.052 mm。不清楚可填“不清楚”。')
    if conflicts:
        labels = ', '.join(LABELS[field][label_index] for field in conflicts)
        clarification = ('Please resolve conflicting records: ' if language == 'en' else '请核实不一致的记录：') + labels
        if questions:
            questions[0] += ('. ' if language == 'en' else '。') + clarification
        else:
            questions.append(clarification)
    if not present(data.get('elements')):
        questions.append('Which elements may be present, including solvents and counterions? You may attach a 2D structure.' if language == 'en'
                         else '可能包含哪些元素（含溶剂和反离子）？也可附上预期二维结构图片。')
    plan = {'schema': 1, 'known_fields': known, 'file_reused_fields': reused,
            'missing_appearance_fields': missing, 'conflicts': conflicts,
            'answered_unknown_fields': answered_unknown, 'questions': questions,
            'known_dimensions_mm': metadata['partial_sizes_mm'] if metadata and 'dimensions_mm' not in conflicts else {},
            'ask_appearance': bool(missing or conflicts), 'ai_calls': 0}
    data['question_plan'] = plan
    return data, plan, metadata


def export_fields(metadata, data):
    """Preserve unchanged file values without claiming a new user measurement."""
    import gemmi
    result = {}
    if not metadata:
        return result
    for field, tags in FIELD_TAGS.items():
        if field in data['question_plan']['conflicts']:
            continue
        for tag in tags:
            if tag in metadata['cif_tokens']:
                token = metadata['cif_tokens'][tag]
                result[tag] = gemmi.cif.as_number(token) if field in {'dimensions_mm', 'temperature'} else gemmi.cif.as_string(token)
    return result
