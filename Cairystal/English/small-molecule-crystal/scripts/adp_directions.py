"""Compare Cartesian ADP axes with saved residual peaks; no automatic disorder claim."""
import argparse,json,math,time
from pathlib import Path
import numpy as np
from structure_diagnostics import structure,newjson
from donor_audit import images
from crystal_runtime import sha,check_stem


def axis_evidence(tensor):
    m=np.asarray(tensor,dtype=float)
    if m.shape!=(3,3) or not np.isfinite(m).all() or not np.allclose(m,m.T):raise ValueError('Finite symmetric Cartesian tensor required')
    w,v=np.linalg.eigh(m)
    if w[0]<=0:return {'status':'NPD','eigenvalues_A2':w.tolist(),'major_axis_cartesian':None,'rms_ratio':None}
    unique=w[2]/w[1]>=1.15
    return dict(status='axis_resolved' if unique else 'major_axis_degenerate',eigenvalues_A2=w.tolist(),
                major_axis_cartesian=v[:,2].tolist() if unique else None,rms_ratio=float(math.sqrt(w[2]/w[0])))


def audit(directory,stem='case',focus=None):
    start=time.perf_counter();check_stem(stem);d=Path(directory);paths={e:d/(stem+'.'+e) for e in ['cif','res']}
    hashes={e:sha(p) for e,p in paths.items()};_,cell,ops,atoms,parsed=structure(paths['cif'],paths['res'])
    requested={x.upper() for x in focus or []};known={a['label'].upper() for a in atoms}
    if requested-known:raise ValueError('Unknown focus atom')
    results=[]
    for atom in atoms:
        if atom['element']=='H' or (requested and atom['label'].upper() not in requested):continue
        if atom['res_context_status']!='matched':raise ValueError('CIF/RES context mismatch')
        if atom['cartesian_tensor'] is None:
            if requested:results.append(dict(atom=atom['label'],status='isotropic_no_axis',peaks=[]))
            continue
        axis=axis_evidence(atom['cartesian_tensor']);candidates=[]
        for q in parsed['peaks']:
            for im in images(cell,ops,atom['xyz'],q['xyz'],2.5):
                if im['distance']<.25:continue
                u=axis['major_axis_cartesian'];angle=None;parallel=None;perp=None
                if u is not None:
                    parallel=abs(float(np.dot(im['vector_cart'],u)))
                    perp=math.sqrt(max(0,im['distance']**2-parallel**2))
                    angle=math.degrees(math.acos(min(1,parallel/im['distance'])))
                candidates.append(dict(label=q['label'],height=q['height'],distance_A=im['distance'],
                    symmetry=im['symmetry'],translation=im['translation'],vector_cart=im['vector_cart'],
                    angle_to_axis_degrees=angle,parallel_A=parallel,perpendicular_A=perp,
                    directional_peak_screen=angle is not None and angle<=30 and q['height']>=.35))
        results.append(dict(atom=atom['label'],part=atom['part'],occupancy=atom['occupancy'],**axis,
            peaks=sorted(candidates,key=lambda p:(not p['directional_peak_screen'],-p['height'],p['distance_A'])),
            disorder_confirmed=False))
    if hashes!={e:sha(p) for e,p in paths.items()}:raise ValueError('Source changed during audit')
    return dict(schema=1,status='evidence_ready',atoms=results,source_sha256=hashes,source_unchanged=True,model_modified=False,
        seconds=round(time.perf_counter()-start,4),limitations=[
            'ADP axes are Cartesian; fractional-coordinate Euclidean angles are not used.',
            'Degenerate or NPD tensors do not provide a reliable unique major direction.',
            'Saved RES Q peaks are incomplete samples of the residual map. Alignment is only a disorder clue, not an atom or occupancy assignment.',
            '0.35 e/A^3, 30 degrees and axis separation 1.15 are screening thresholds, not crystallographic correctness criteria.'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',required=True);p.add_argument('--stem',default='case')
    p.add_argument('--atoms',nargs='+');p.add_argument('--output',required=True);a=p.parse_args()
    try:r=audit(a.directory,a.stem,a.atoms);newjson(a.output,r);print(json.dumps({'status':r['status'],'atoms':len(r['atoms']),'seconds':r['seconds']}));return 0
    except Exception as e:print(json.dumps({'status':'failed','error':str(e)}));return 2
if __name__=='__main__':raise SystemExit(main())
