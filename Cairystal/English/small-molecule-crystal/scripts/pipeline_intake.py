"""Bounded raw-data intake; no recursive discovery or reference-model reads."""
import importlib,json,math,platform,re,sys
from pathlib import Path
from crystal_runtime import regular,sha,write_json,utc_now

def unlinked(path):
    p=Path(path).absolute()
    for item in [p,*p.parents]:
        if item.is_symlink() or getattr(item,'is_junction',lambda:False)():raise ValueError('Linked/junction paths require a separately scoped job: '+str(item))
    return p

def bootstrap(profile):
    for path in reversed(profile.get('module_dirs',[])):
        p=unlinked(path)
        if not p.is_dir():raise ValueError('Configured Python module directory missing: '+str(p))
        if str(p) not in sys.path:sys.path.insert(0,str(p))
    required=['gemmi','docx','pypdf']
    for name in required:importlib.import_module(name)

def build_profile(software,renderer,pdftoppm,powershell=None,soffice=None,module_dirs=()):
    folder=unlinked(software)
    value={'schema':1,'created_at':utc_now(),'python':sys.executable,'python_version':sys.version,'platform':platform.platform(),
           'module_dirs':[str(unlinked(p)) for p in module_dirs],'renderer':renderer,'tools':{},'execution_verified':False}
    paths={k:folder/(k+'.exe') for k in ['shelxt','shelxl','platon']}
    if (folder/'shelxd.exe').is_file():paths['shelxd']=folder/'shelxd.exe'
    paths['pdftoppm']=pdftoppm
    if renderer=='word':paths['powershell']=powershell
    elif renderer=='libreoffice':paths['soffice']=soffice
    else:raise ValueError('Unsupported document renderer')
    for name,path in paths.items():
        if not path:raise ValueError('Missing configured executable: '+name)
        p=regular(unlinked(path));value['tools'][name]={'path':str(p),'sha256':sha(p)}
    bootstrap(value)
    value['modules']={n:getattr(importlib.import_module(n),'__version__',None) for n in ['gemmi','docx','pypdf']}
    from runtime_capabilities import inspect as inspect_capabilities
    value['capabilities']=inspect_capabilities()
    return value

def verify_profile(value):
    bootstrap(value)
    for name,item in value['tools'].items():
        if sha(regular(unlinked(item['path'])))!=item['sha256']:raise ValueError('Configured executable changed; refresh profile: '+name)
    if Path(value['python']).resolve()!=Path(sys.executable).resolve():raise ValueError('Use the Python executable recorded in the profile')
    return {k:v['path'] for k,v in value['tools'].items()}

def normalize_elements(elements):
    import gemmi
    if not elements:raise ValueError('Provide every possible element, including solvent/counterion elements')
    normalized=[]
    for name in elements:
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z]{1,2}',name):raise ValueError('Use chemical element symbols: '+str(name))
        try:e=gemmi.Element(name)
        except Exception:raise ValueError('Unknown element: '+str(name))
        if not e.atomic_number or e.name.upper()=='D':raise ValueError('Unsupported element/isotope for this routine X-ray initializer: '+str(name))
        if e.name not in normalized:normalized.append(e.name)
    if not any(n!='H' for n in normalized):raise ValueError('At least one non-H element is required')
    return normalized

def discover(directory,stem=None):
    """List only immediate original HKL/P4P paths. Never open RES/CIF/INS."""
    directory=unlinked(directory)
    if not directory.is_dir():raise ValueError('Input directory missing')
    names={p.name.lower():p for p in directory.iterdir() if p.is_file()}
    choices=[p for key,p in names.items() if key.endswith('.hkl') and p.with_suffix('.p4p').name.lower() in names]
    if stem:
        if Path(stem).name!=stem or '/' in stem or '\\' in stem:raise ValueError('Stem must be a basename')
        choices=[p for p in choices if p.stem.lower()==stem.lower()]
    if len(choices)!=1:raise ValueError('Require exactly one same-basename original HKL/P4P pair; select --stem if ambiguous. Found: '+', '.join(p.stem for p in choices))
    hkl=choices[0];base=hkl.stem;reduced=re.sub(r'_\d+m$','',base,flags=re.I)
    selected={'hkl':hkl,'p4p':names[hkl.with_suffix('.p4p').name.lower()]}
    log=names.get((base+'._ls').lower())
    if log:selected['integration_log']=log
    absorption=[names[x.lower()] for x in dict.fromkeys([base+'.abs',reduced+'.abs']) if x.lower() in names]
    if len(absorption)>1:raise ValueError('Ambiguous absorption logs; explicit provenance review required')
    if absorption:selected['absorption_log']=absorption[0]
    for p in selected.values():regular(unlinked(p))
    from project_metadata_preflight import inventory
    companion_inventory=inventory(directory,base)
    companions=[item['path'] for item in companion_inventory['candidates']]
    return selected,{'pairing_basis':'Identical HKL/P4P basename; optional integration same basename; absorption same basename or removal of Bruker _Nm suffix, recorded for review.',
                     'additional_metadata_not_read':companions,'metadata_companion_inventory':companion_inventory,
                     'missing_metadata_source_hint':'If fields are missing, inspect permitted same-project metacif/phil/PCF/cif_od with project_metadata_preflight.py; metadata presence and filenames do not prove pairing.',
                     'scope':'Raw inputs from immediate directory; root/olex2 companion names only. RES, CIF, INS, companion contents, literature and historical results are not opened by discovery.'}

def validate_specimen(path):
    if not path:return {},['colour','habit','three_dimensions']
    allowed={'_exptl_crystal_colour','_exptl_crystal_description','_exptl_crystal_size_max','_exptl_crystal_size_mid','_exptl_crystal_size_min','_diffrn_measurement_device_type','_diffrn_ambient_temperature','_diffrn_radiation_type'}
    value=json.loads(regular(unlinked(path)).read_text(encoding='utf-8-sig'));fields=value.get('cif_fields',{})
    if not value.get('provenance'):raise ValueError('Specimen facts need a provenance statement')
    if set(fields)-allowed:raise ValueError('Specimen file contains unsupported fields')
    if value.get('draft_defaults') or value.get('confirmed') is False:raise ValueError('Draft specimen defaults must not be submitted as measured facts')
    if '_diffrn_ambient_temperature' in fields:
        t=float(fields['_diffrn_ambient_temperature'])
        if not math.isfinite(t) or t<=0:raise ValueError('Invalid confirmed diffraction temperature in K')
    dims=[fields.get('_exptl_crystal_size_'+x) for x in ['max','mid','min']]
    if any(v is not None for v in dims):
        numbers=[float(v) for v in dims if v is not None]
        if any(not math.isfinite(x) or x<=0 for x in numbers) or numbers!=sorted(numbers,reverse=True):raise ValueError('Dimensions must be positive mm values with max >= mid >= min')
    missing=[x for x,t in [('colour','_exptl_crystal_colour'),('habit','_exptl_crystal_description')] if not fields.get(t)]
    if any(v is None for v in dims):missing.append('three_dimensions')
    return value,missing

def inspect(directory,elements,stem=None,specimen=None):
    from crystal_session import parse_p4p,laue_seed
    from inspect_case import reflection_stats
    selected,scope=discover(directory,stem);normalized=normalize_elements(elements)
    p4p_bytes=selected['p4p'].read_bytes()
    meta=parse_p4p(p4p_bytes.decode('latin1'))
    import gemmi
    if any(not math.isfinite(v) for v in meta['cell']) or any(v<=0 for v in meta['cell'][:3]) or any(not 0<v<180 for v in meta['cell'][3:]) or not math.isfinite(meta['wavelength']) or meta['wavelength']<=0:raise ValueError('Nonphysical cell/wavelength')
    volume=gemmi.UnitCell(*meta['cell']).volume
    if not math.isfinite(volume) or volume<=0:raise ValueError('Nonphysical unit-cell volume')
    # Optional cell-measurement subset is validated by the shared P4P parser;
    # missing SAINGL is not replaced with the complete HKL theta/count.
    stats=reflection_stats(selected['hkl'])
    if not stats['standard_layout_recognized']:raise ValueError('Unrecognized reflection format: '+str(stats['format_issue_samples']))
    if stats.get('routine_hkl4_issue'):
        raise ValueError('Routine HKLF 4 needs input review: '+str(stats['routine_hkl4_issue']))
    laue=laue_seed(meta,selected['hkl'])
    fact,missing=validate_specimen(specimen)
    from p4p_metadata import input_conflicts
    meta['input_conflicts']=input_conflicts(meta,normalized,fact)
    result={'inputs':{k:{'path':str(p),'sha256':sha(p)} for k,p in selected.items()},'elements':normalized,'sfac_order':normalized,'metadata':meta,'laue_seed':laue,'hkl_statistics':stats,'specimen':fact,'missing_specimen_facts':missing,**scope}
    import hashlib
    if result['inputs']['p4p']['sha256'] != hashlib.sha256(p4p_bytes).hexdigest():
        raise ValueError('P4P changed during intake')
    if 'laue_screen' in meta and result['inputs']['hkl']['sha256'] != meta['laue_screen']['hkl_sha256']:
        raise ValueError('HKL changed during Laue screening')
    if specimen:result['inputs']['specimen']={'path':str(regular(unlinked(specimen))),'sha256':sha(specimen)}
    return result
