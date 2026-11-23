"""Verify this extracted package against SHA256SUMS.json (not a signature)."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import sys

def verify(root):
    root = Path(root).absolute()
    def no_links(p):
        for q in (p, *p.parents):
            if q.is_symlink() or getattr(q,'is_junction',lambda:False)():
                raise ValueError('Linked package paths are not accepted')
    no_links(root)
    manifest = root / 'SHA256SUMS.json'
    no_links(manifest)
    expected = json.loads(manifest.read_text('utf-8'))
    if not isinstance(expected, dict) or not expected:
        raise ValueError('Invalid manifest')
    for name, sha in expected.items():
        rel = PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts or ':' in name or '\\' in name:
            raise ValueError('Invalid manifest path: '+name)
        p = root / rel
        no_links(p)
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != sha:
            raise ValueError('Missing or changed file: '+name)
    found=set()
    for p in root.rglob('*'):
        no_links(p)
        if p.is_file() and p != manifest and '__pycache__' not in p.parts and p.suffix not in {'.pyc','.pyo'}:
            found.add(p.relative_to(root).as_posix())
    if found != set(expected):
        raise ValueError('Unexpected package files: '+str(sorted(found-set(expected))))
    return {'status':'integrity_verified','files':len(expected),'publisher_authenticated':False}

if __name__ == '__main__':
    try:
        print(json.dumps(verify(Path(__file__).resolve().parent)))
    except (OSError, ValueError) as exc:
        print(json.dumps({'status':'integrity_failed','error':str(exc)}),file=sys.stderr)
        raise SystemExit(2)
