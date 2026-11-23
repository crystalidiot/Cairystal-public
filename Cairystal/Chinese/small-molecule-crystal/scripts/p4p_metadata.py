"""Original P4P metadata with dialect-aware provenance, never model coordinates."""
import math
import re
import gemmi
from p4p_provenance import require_experimental_p4p


def read_p4p(text, require_core=True, temperature_unit=None, temperature_basis=None):
    require_experimental_p4p(text)
    rows = {}
    for line in text.splitlines():
        parts = line.split()
        if parts:
            rows.setdefault(parts[0].upper(), []).append(parts[1:])

    def field(key, required=False, count=None):
        values = rows.get(key, [])
        if not values:
            if required:
                raise ValueError('P4P field missing: ' + key)
            return None
        checked = [v[:count] if count else v for v in values]
        if any(v != checked[0] for v in checked[1:]):
            raise ValueError('Conflicting P4P ' + key + ' records')
        if count and len(checked[0]) < count:
            raise ValueError('Incomplete P4P ' + key)
        return checked[0]

    def numbers(values, key):
        result = list(map(float, values))
        if not all(math.isfinite(v) for v in result):
            raise ValueError('Non-finite P4P ' + key)
        return result

    fileid = ' '.join(field('FILEID') or [])
    dialect = 'bruker_saint' if re.match(r'SAINT\b', fileid, re.I) else 'rigaku_rapidauto' if re.match(r'Rigaku\s+RapidAuto', fileid, re.I) else 'unknown'
    result = {'dialect': dialect, 'fileid': fileid, 'warnings': [],
              'measurement_reflections': None, 'measurement_theta_min': None,
              'measurement_theta_max': None, 'field_provenance': {}}
    cell = field('CELL', require_core, 6)
    if cell:
        cell = numbers(cell, 'CELL')
        if any(v <= 0 for v in cell[:3]) or any(not 0 < v < 180 for v in cell[3:]):
            raise ValueError('Nonphysical P4P CELL')
        volume = gemmi.UnitCell(*cell).volume
        if not math.isfinite(volume) or volume <= 0:
            raise ValueError('Nonphysical P4P cell volume')
        result['cell'] = cell
    sd = field('CELLSD', require_core, 6)
    if sd:
        result['cell_su'] = numbers(sd, 'CELLSD')
        if any(v < 0 for v in result['cell_su']):
            raise ValueError('Negative P4P CELLSD')
    source = field('SOURCE', require_core, 2)
    if source:
        wavelength = numbers(source[1:2], 'SOURCE')[0]
        if wavelength <= 0:
            raise ValueError('Invalid P4P wavelength')
        result.update(wavelength=wavelength, radiation=source[0])
    bravais = field('BRAVAIS')
    if bravais == []:
        raise ValueError('Empty P4P BRAVAIS declaration')
    if bravais:
        result['bravais'] = ' '.join(bravais)
    result['declared_symmetry'] = field('SYMM') or []
    subset = field('SAINGL', count=3)
    if subset and not any(v in {'?', '.'} for v in subset):
        n, lo, hi = numbers(subset, 'SAINGL')
        if n <= 0 or int(n) != n or not 0 <= lo <= hi <= 90:
            raise ValueError('Invalid measured cell-refinement count/theta values')
        result.update(measurement_reflections=int(n), measurement_theta_min=lo, measurement_theta_max=hi)
        result['field_provenance']['cell_measurement'] = 'Original SAINGL[0:3]; not LIMITS or the HKL resolution range'
    else:
        result['warnings'].append('Cell-measurement count/theta absent; left unknown, not a prerequisite for solving.')
    csize = field('CSIZE') or []
    result['reported_chem'] = ' '.join(field('CHEM') or [])
    result['reported_dimensions_raw'] = csize[:3]
    raw = csize[4] if len(csize) > 4 else '?'
    unit = 'C' if dialect == 'bruker_saint' else None
    basis = 'FILEID SAINT: Bruker CSIZE temperature in degrees Celsius' if unit else None
    if temperature_unit is not None:
        if temperature_unit not in {'K', 'C'} or not temperature_basis:
            raise ValueError('An explicit P4P temperature unit needs K/C and documented basis')
        if unit and unit != temperature_unit:
            raise ValueError('Temperature unit conflicts with recognized P4P dialect')
        unit, basis = temperature_unit, temperature_basis
    result['temperature_evidence'] = {'raw': raw, 'unit': unit, 'basis': basis, 'status': 'missing'}
    if raw not in {'?', '.'}:
        value = numbers([raw], 'CSIZE temperature')[0]
        # Both physically possible units are rejected for values below absolute zero.
        if value <= -273.15:
            raise ValueError('Invalid P4P CSIZE temperature')
        if unit is None:
            result['temperature_evidence']['status'] = 'unit_unconfirmed'
            result['warnings'].append('CSIZE temperature unit unconfirmed; raw value retained, no automatic K/C conversion.')
        else:
            kelvin = value + 273.15 if unit == 'C' else value
            if kelvin <= 0:
                raise ValueError('Invalid P4P CSIZE temperature')
            result['temperature_K'] = round(kelvin, 6)
            result['temperature_evidence']['status'] = 'resolved'
    return result


def input_conflicts(meta, elements, specimen):
    """Report template-like CHEM/SIZE conflicts; never import them as observations."""
    result = []
    text = meta.get('reported_chem', '')
    symbols = set(re.findall(r'\b([A-Z][a-z]?)(?=\d|\s|$)', text))
    declared = set(elements)
    if symbols and symbols != declared:
        result.append({'field': 'CHEM', 'raw': text, 'user_elements': elements,
                       'decision': 'Use explicitly supplied possible elements, not P4P stoichiometry.'})
    sizes = meta.get('reported_dimensions_raw', [])
    actual = specimen.get('cif_fields', {})
    given = [actual.get('_exptl_crystal_size_' + k) for k in ('max', 'mid', 'min')]
    try:
        old = sorted(map(float, sizes), reverse=True)
        if len(old) == 3 and all(v is not None for v in given) and any(abs(a-float(b)) > 1e-6 for a,b in zip(old,given)):
            result.append({'field': 'CSIZE dimensions', 'raw': sizes, 'confirmed_mm': given,
                           'decision': 'Use confirmed specimen dimensions; preserve conflicting raw fields.'})
    except (ValueError, TypeError):
        pass
    return result
