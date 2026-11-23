"""Read-only source integrity check. Hashes do not authenticate a publisher."""
import argparse,hashlib,json
from pathlib import Path

def verify(skill,manifest):
 root=Path(skill).absolute();mp=Path(manifest).absolute()
 def no_links(p):
  for q in (p,*p.parents):
   if q.is_symlink() or (hasattr(q,'is_junction') and q.is_junction()):raise ValueError('Release path traverses a link')
 no_links(root);no_links(mp)
 expected=json.loads(mp.read_text(encoding='utf-8-sig'))
 if not isinstance(expected,dict) or not expected:raise ValueError('Empty or invalid release manifest')
 for name,digest in expected.items():
  rel=Path(name)
  if rel.is_absolute() or '..' in rel.parts or ':' in name or '\\' in name:raise ValueError('Invalid manifest path')
  path=root/rel;no_links(path)
  if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Release file mismatch: '+name)
 actual=set()
 for path in root.rglob('*'):
  no_links(path)
  if path.is_file() and '__pycache__' not in path.parts and path.suffix not in {'.pyc','.pyo'}:actual.add(path.relative_to(root).as_posix())
 if actual!=set(expected):raise ValueError('Unlisted release files: '+str(sorted(actual-set(expected))))
 return {'status':'integrity_verified','files':len(expected),'manifest_sha256':hashlib.sha256(mp.read_bytes()).hexdigest(),'publisher_authenticated':False}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--skill',required=True);p.add_argument('--manifest',required=True);a=p.parse_args()
 print(json.dumps(verify(a.skill,a.manifest),ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
