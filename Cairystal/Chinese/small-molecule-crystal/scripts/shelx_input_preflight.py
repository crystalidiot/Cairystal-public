"""Mechanical SHELX input checks and bounded formatting, no chemical decisions."""
import math
import re


CONTINUABLE = {'SFAC','UNIT','DFIX','DANG','SADI','SAME','SIMU','DELU','RIGU',
               'ISOR','EADP','EXYZ','ANIS','BOND','CONF','HTAB','OMIT'}


def render_records(rows):
    output = []
    for row in rows:
        line = row if isinstance(row, str) else ' '.join(row)
        if '\n' in line or '\r' in line:
            raise ValueError('Each input item must be one SHELX logical record')
        if not line.strip():
            output.append(''); continue
        key = line.split()[0].upper()
        comment = key in {'REM', 'TITL'}
        while len(line) > 76:
            cut = line.rfind(' ', 0, 72)
            if cut < 1:
                raise ValueError('Unbreakable SHELX record')
            if comment:
                output.append(line[:cut]); line = 'REM ' + line[cut:].lstrip()
            else:
                atom = False
                parts = line.split()
                if len(parts) >= 7:
                    try:
                        atom = int(parts[1]) > 0
                        list(map(float, parts[2:7]))
                    except ValueError:
                        pass
                if key not in CONTINUABLE and not atom:
                    raise ValueError('Long instruction needs an explicit formatting rule: ' + key)
                output.append(line[:cut] + ' ='); line = '    ' + line[cut:].lstrip()
        output.append(line)
    return '\n'.join(output) + '\n'


def validate_native_input(text):
    from crystal_runtime import check_instructions
    active = False
    for index, raw in enumerate(text.splitlines(), 1):
        if len(raw.expandtabs(8)) > 80:
            raise ValueError(f'SHELX physical line {index} exceeds 80 columns; reformat the derived input')
        if re.match(r'^\s*REM\b', raw, re.I) and raw.rstrip().endswith('='):
            raise ValueError(f'REM continuation is unsafe at line {index}; use repeated REM lines')
        if re.match(r'^\s*CELL\b', raw, re.I): active = True
        if active and re.match(r'^\s*HKLF\b', raw, re.I): break
    rows = check_instructions(text)
    names = [r[0].upper() for r in rows]
    for key in ['CELL','LATT','UNIT','TEMP','SIZE','WGHT','LIST']:
        if names.count(key) > 1:
            raise ValueError('Duplicate active SHELX instruction: ' + key)
    sfac = [r[1:] for r in rows if r[0].upper() == 'SFAC']
    simple = all(re.fullmatch(r'[A-Za-z]{1,2}', v) for r in sfac for v in r)
    count = sum(map(len, sfac)) if simple else None
    unit = next(r[1:] for r in rows if r[0].upper() == 'UNIT')
    if count is not None and len(unit) != count:
        raise ValueError('UNIT count does not match SFAC order')
    if any(not math.isfinite(float(v)) or float(v) < 0 for v in unit):
        raise ValueError('Invalid UNIT values')
    controls = CONTINUABLE | {'CELL','ZERR','LATT','SYMM','TEMP','SIZE','WGHT','LIST',
                             'HKLF','FVAR','L.S.','CGLS','TWIN','BASF','AFIX','HFIX','PART','RESI'}
    checked_atoms = 0
    for r in rows:
        if r[0].upper() in controls or len(r) < 7 or not re.fullmatch(r'\d+', r[1]): continue
        values = list(map(float, r[2:7]))
        if not all(map(math.isfinite, values)):
            raise ValueError('Non-finite atom parameters: ' + r[0])
        if count is not None and not 1 <= int(r[1]) <= count:
            raise ValueError('Atom SFAC index out of range: ' + r[0])
        checked_atoms += 1
    return {'status': 'passed', 'sfac_count': count, 'checked_atom_records': checked_atoms,
            'scope': 'Syntax and active controls, not structural correctness'}
