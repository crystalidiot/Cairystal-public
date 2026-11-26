"""Local deployment adapter. Portable tools remain in cairystal.py and toolbox.json.

One implementation serves standard/fast project aliases. Existing jobs continue
from their pinned release, not the current pointer. No upload consent is added.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ALIASES = {'verify-source':'verify', 'platon-check':'platon', 'squeeze-request':'squeeze'}
# The historical bare squeeze command called the lower-level workflow, while
# the toolbox's squeeze tool exposes the request/consent wrapper. Keep both.
DIRECT = {'squeeze': ('squeeze_workflow.py', [])}
DISCOVERY = {'guide', 'version', 'workflow', 'list', 'describe', 'plan', 'run'}

def read(path):
    return json.loads(Path(path).read_text('utf-8-sig'))

def resolve(root, channel='standard'):
    root = Path(root).resolve()
    record = read(root / ('Cairystal.fast.json' if channel == 'fast' else 'Cairystal.current.json'))
    skill, profile = Path(record['skill']).resolve(), Path(record['profile']).resolve()
    info = read(skill / 'release_info.json')
    if record['release'] != info['release_id']:
        raise ValueError('Pointer release differs from selected skill release_info.json')
    return record, skill, profile

def verify(record, skill, profile):
    digest = hashlib.sha256(profile.read_bytes()).hexdigest()
    if record.get('profile_sha256') and digest != record['profile_sha256']:
        raise ValueError('Pinned runtime profile changed')
    manifest = read(record.get('release_manifest', skill.parent/'release_manifest.json'))
    for rel, expected in manifest.items():
        path = skill / rel
        if not path.resolve().is_relative_to(skill) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Pinned release file changed: ' + rel)

def dispatch(root, argv):
    argv = list(argv)
    channel = 'standard'
    if argv[:1] == ['--channel']:
        if len(argv) < 2 or argv[1] not in ('standard','fast'):
            raise ValueError('Choose --channel standard or fast')
        channel, argv = argv[1], argv[2:]
    record, skill, profile = resolve(root, channel)
    if not argv or argv[0] == 'info':
        print(json.dumps({**record,'channel':channel,'skill':str(skill),
                          'entry':str(skill/'cairystal.py')},ensure_ascii=False,indent=2))
        return 0
    verify(record, skill, profile)
    config = read(profile)
    command = argv[0]; rest = argv[1:]
    direct = None
    if command in DIRECT:
        script, prefix = DIRECT[command]
        if '--profile' not in rest:
            rest += ['--profile',str(profile)]
        direct = [str(skill/'scripts'/script),*prefix,*rest]
        forwarded = []
    elif command == 'toolbox':
        forwarded = rest
    elif command in DISCOVERY or command in ('--help','-h','--language'):
        forwarded = argv
    else:
        # Old project commands translate to the single registered toolbox.
        tool = ALIASES.get(command, command)
        registered = {t['id'] for t in read(skill/'assets/toolbox.json')['tools']}
        if tool not in registered:
            raise ValueError('Unknown command; use list, describe TOOL, or run TOOL -- <arguments>')
        if command in {'doctor','intake-accept','squeeze','complete','platon-check'} and '--profile' not in rest:
            rest += ['--profile',str(profile)]
        if (command == 'pipeline' and rest[:1] == ['start'] or command == 'squeeze-request' and rest[:1] == ['execute']) and '--profile' not in rest:
            rest += ['--profile',str(profile)]
        forwarded = ['run',tool,'--',*rest]
    if channel == 'fast' and forwarded[:4] == ['run','autorun','--','run'] and '--execution-mode' not in forwarded:
        forwarded += ['--execution-mode','fast']
    env = os.environ.copy()
    env['PYTHONUTF8'] = '1'
    env['PYTHONPATH'] = os.pathsep.join([*config.get('module_dirs',[]), *([env['PYTHONPATH']] if env.get('PYTHONPATH') else [])])
    target = direct if direct is not None else [str(skill/'cairystal.py'),*forwarded]
    return subprocess.call([config['python'],'-B',*target],env=env,shell=False)

def main(root, argv):
    try:
        return dispatch(root, argv)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(json.dumps({'status':'blocked','error':str(exc)},ensure_ascii=False),file=sys.stderr)
        return 2
