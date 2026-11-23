"""Evidence for PLATON completion and selected rules, without guessed missing files."""
from pathlib import Path
import os,re,hashlib

def rules_context(executable):
    folder=Path(executable).absolute().parent
    environment=os.environ.get('CHECKDEF')
    paths=[folder/'check.def']+([Path(environment)] if environment else [])
    return {'CHECKDEF':environment,'external_rule_files':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None for p in paths},'absence_of_external_file_is_not_failure':True}

def native_versions(text):
    m=re.search(r'PLATON/CHECK-\((\d+)\)\s+versus\s+check[.]def\s+version\s+(\d+)',text,re.I)
    return {'platon_version':m[1] if m else None,'checkdef_version':m[2] if m else None,'evidence':'native validation report header'}

def validation_ready(folder,stem):
    from parse_platon_alerts import parse
    folder=Path(folder);files=[folder/f'{stem}.chk',folder/f'{stem}.ckf']
    if not all(p.is_file() and p.stat().st_size>100 for p in files):return False
    log=folder/'platon.out'
    if not log.exists():return False
    text=log.read_text('latin1')
    if 'CheckCIF' not in text or 'CheckFCF' not in text:return False
    try:r=parse(files[0].read_text('latin1'))
    except (ValueError,IndexError):return False
    return bool(r['report_footer_present'] and not r['warnings'])

def completion_fingerprint(folder,stem):
    """Extra completion evidence after validation_ready, for a shorter settle wait.

    Require native output notices, matching plot count, and a closed PostScript
    trailer. Unknown versions/formats retain the conservative completion path.
    Hash contents, not only sizes, so equal-size rewrites reset the settling clock.
    """
    folder=Path(folder)
    names=[stem+'.chk',stem+'.ckf','platon.out',stem+'.ps']
    try:
        content={name:(folder/name).read_bytes() for name in names}
        log=content['platon.out'].decode('latin1');ps=content[stem+'.ps'].decode('latin1')
        for kind,extension in [('CheckCIF','chk'),('CheckFCF','ckf')]:
            if not re.search(r'::\s*'+kind+r'\s+out on\s*:\s*'+re.escape(stem+'.'+extension)+r'\s',log):return None
        notice=re.search(r'::\s*CheckPlots\s+on\s*:\s*'+re.escape(stem+'.ps')+r'\s*\[\s*(\d+)\s+Plots?\s*\]',log)
        pages=re.findall(r'^%%Pages:\s*(\d+)\s*$',ps,re.M)
        if not notice or not pages or int(notice[1])!=int(pages[-1]) or not ps.rstrip().endswith('%%EOF') or not ps.startswith('%!PS'):return None
        return {name:hashlib.sha256(data).hexdigest() for name,data in content.items()}
    except OSError:return None

def embedded_reflections(cif):
    """Permit native reconstruction only when the CIF actually supplies input data."""
    import gemmi
    b=gemmi.cif.read_file(str(cif)).sole_block()
    hkl=b.find_value('_shelx_hkl_file');res=b.find_value('_shelx_res_file')
    if hkl and res and len(gemmi.cif.as_string(hkl))>100 and len(gemmi.cif.as_string(res))>100:
        return 'embedded_SHELX_HKL_and_RES_native_reconstruction'
    tags=['_refln_index_h','_refln_index_k','_refln_index_l','_refln_F_squared_calc','_refln_F_squared_meas','_refln_F_squared_sigma']
    if len(b.find(tags))>0:return 'embedded_structure_factor_loop'
    raise ValueError('No paired FCF or supported embedded reflections; do not claim full local validation')
