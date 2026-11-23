"""Create an external Cairystal runtime profile without executing native programs."""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import platform
import sys
from datetime import datetime, timezone

def plain(path):
    p = Path(path).absolute()
    for q in (p, *p.parents):
        if q.is_symlink() or getattr(q, 'is_junction', lambda: False)():
            raise ValueError('Linked paths are not accepted: ' + str(q))
    return p

def create(args):
    package = Path(__file__).resolve().parent
    output = plain(args.output)
    if output.is_relative_to(package):
        raise ValueError('Store machine profiles outside the frozen package')
    if output.exists():
        raise FileExistsError('Use a new profile path; existing files are never overwritten')
    skill = plain(args.skill)
    if not (skill / 'SKILL.md').is_file() or not (skill / 'scripts/pipeline_intake.py').is_file():
        raise ValueError('Not a complete Cairystal skill directory')
    paths = {n:getattr(args,n) for n in ('shelxt','shelxl','platon','pdftoppm')}
    if args.renderer == 'word':
        paths['powershell'] = args.powershell
    else:
        paths['soffice'] = args.soffice
    if args.shelxd:
        paths['shelxd'] = args.shelxd
    tools = {}
    for name, value in paths.items():
        if not value:
            raise ValueError('Missing path: ' + name)
        p = plain(value)
        if not p.is_file():
            raise FileNotFoundError('Executable not found: ' + str(p))
        tools[name] = {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    module_dirs = []
    for value in args.module_dir:
        p = plain(value)
        if not p.is_dir():
            raise FileNotFoundError('Module directory not found: ' + str(p))
        module_dirs.append(str(p))
    for value in reversed(module_dirs):
        sys.path.insert(0, value)
    sys.path.insert(0, str(skill / 'scripts'))
    from runtime_capabilities import inspect
    from pipeline_intake import verify_profile
    caps = inspect()
    missing = [n for n, value in caps['modules'].items() if not value['available']]
    if missing:
        raise ValueError('Install requirements.txt using this Python; missing: ' + ', '.join(missing))
    profile = {'schema':1,'created_at':datetime.now(timezone.utc).isoformat(),
               'python':sys.executable,'python_version':sys.version,'platform':platform.platform(),
               'module_dirs':module_dirs,'renderer':args.renderer,'tools':tools,
               'modules':{n:getattr(importlib.import_module(n),'__version__',None) for n in ('gemmi','docx','pypdf')},
               'capabilities':caps,'execution_verified':False,
               'configuration_scope':'File/hash/import checks only; native engines, document renderer and IUCr service not executed.'}
    verify_profile(profile)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as stream:
        json.dump(profile, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    return {'status':'profile_created','profile':str(output),'native_execution_verified':False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--skill', required=True)
    for name in ('shelxt','shelxl','platon','pdftoppm'):
        p.add_argument('--'+name, required=True)
    p.add_argument('--shelxd')
    p.add_argument('--renderer', choices=('word','libreoffice'), required=True)
    p.add_argument('--powershell')
    p.add_argument('--soffice')
    p.add_argument('--module-dir', action='append', default=[])
    p.add_argument('--output', required=True)
    try:
        result = create(p.parse_args())
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError, ImportError) as exc:
        print(json.dumps({'status':'configuration_error','error':str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2

if __name__ == '__main__':
    raise SystemExit(main())
