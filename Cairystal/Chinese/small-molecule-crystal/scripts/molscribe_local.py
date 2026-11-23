"""Read image-only manifest, run a pinned local checkpoint, emit reviewable chemical graphs.

No reference SMILES, previous crystal coordinates or LLM API is read. Predictions
remain hypotheses: confidence scores are not calibrated correctness probabilities.
"""
import argparse,hashlib,json,os,time,traceback
from pathlib import Path

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()
def safe(p):
    p=Path(p).absolute()
    if any(x.is_symlink() or getattr(x,'is_junction',lambda:False)() for x in [p,*p.parents]):raise ValueError('Linked paths rejected')
    return p
def json_default(v):
    if hasattr(v,'tolist'):return v.tolist()
    if hasattr(v,'item'):return v.item()
    raise TypeError(type(v).__name__)
def write(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False,default=json_default),encoding='utf-8')
def chemical_graph(prediction,allowed_elements=None):
    from rdkit import Chem
    from rdkit.Chem import rdMolDescriptors
    issues=[];smiles=prediction.get('smiles','');mol=Chem.MolFromSmiles(smiles) if smiles else None
    if mol is None or not mol.GetNumAtoms():return {'status':'invalid_prediction','issues':['No valid nonempty chemical graph'],'graph':None}
    atoms=[];bonds=[];elements=set()
    for atom in mol.GetAtoms():
        symbol=atom.GetSymbol();elements.add(symbol)
        row={'id':'a'+str(atom.GetIdx()+1),'element':symbol,'formal_charge':atom.GetFormalCharge(),'hydrogens':int(atom.GetTotalNumHs())}
        if atom.GetIsotope():row['isotope']=atom.GetIsotope();issues.append('Isotope handling requires review')
        if atom.GetAtomicNum()==0:issues.append('Unresolved R-group/abbreviation/dummy atom')
        if symbol in {'H','D'}:issues.append('Explicit H/isotope sites require dedicated conversion')
        if atom.GetNumRadicalElectrons():issues.append('Radical electronic state requires review')
        if atom.GetChiralTag()!=Chem.ChiralType.CHI_UNSPECIFIED:row['chiral_tag']=str(atom.GetChiralTag());issues.append('Explicit stereochemistry outside current automatic matcher')
        if symbol=='N' and atom.GetHybridization()==Chem.HybridizationType.SP2:row['geometry']='planar'
        atoms.append(row)
    for bond in mol.GetBonds():
        order=bond.GetBondTypeAsDouble()
        if order not in (1,1.5,2,3):issues.append('Unsupported bond type')
        if bond.GetStereo()!=Chem.BondStereo.STEREONONE:issues.append('Double-bond stereochemistry outside current automatic matcher')
        bonds.append(['a'+str(bond.GetBeginAtomIdx()+1),'a'+str(bond.GetEndAtomIdx()+1),order])
    fragments=len(Chem.GetMolFrags(mol))
    if fragments>1:issues.append('Multiple components: confirm solvents/counterions and their multiplicities')
    if allowed_elements is not None and elements-set(allowed_elements):issues.append('Predicted elements outside the explicitly supplied set')
    confidences=[float(prediction.get('confidence',0))]+[float(a.get('confidence',0)) for a in prediction.get('atoms',[])]+[float(b.get('confidence',0)) for b in prediction.get('bonds',[])]
    minimum=min(confidences)
    if minimum<.90:issues.append('Model/atom/bond confidence below experimental 0.90 screen; threshold is not calibrated')
    graph={'source':'Local MolScribe image recognition; not an observed crystal model or an accepted chemical identity. Review image, stoichiometry and protonation before use.',
           'hypothesis':True,'local_recognition':True,'smiles':Chem.MolToSmiles(mol,isomericSmiles=True),'atoms':atoms,'bonds':bonds}
    if any('stereochemistry' in x for x in issues):graph['stereochemistry']='Requires review; retained in source SMILES'
    return {'status':'needs_review' if issues else 'candidate_ready_for_review','issues':sorted(set(issues)),
            'graph':graph,'formula':rdMolDescriptors.CalcMolFormula(mol),'components':fragments,
            'minimum_model_confidence':minimum,'element_set':sorted(elements),
            'automatic_scientific_acceptance':False}

def run(manifest,checkpoint,output,device='cuda'):
    start=time.perf_counter();manifest=safe(manifest);checkpoint=safe(checkpoint);output=safe(output)
    if output.exists():raise ValueError('Use a new prediction directory')
    spec=json.loads(manifest.read_text(encoding='utf-8-sig'))
    if set(spec)-{'schema','cases','checkpoint_sha256'}:raise ValueError('Only image-only inference manifest fields allowed')
    if not spec.get('checkpoint_sha256') or sha(checkpoint)!=spec['checkpoint_sha256']:raise ValueError('Pinned model SHA256 mismatch')
    cases=spec['cases'];seen=set()
    for case in cases:
        if set(case)-{'case_id','image','image_sha256','elements'}:raise ValueError('Reference/answer fields are forbidden in inference inputs')
        cid=case['case_id']
        if not isinstance(cid,str) or not cid.isalnum() or cid in seen:raise ValueError('Unique alphanumeric case_id required')
        seen.add(cid)
        if sha(safe(case['image']))!=case['image_sha256']:raise ValueError('Image hash changed')
    output.mkdir(parents=True);write(output/'input_used.json',spec)
    os.environ.setdefault('OMP_NUM_THREADS','4')
    import torch,numpy as np
    from PIL import Image
    from molscribe import MolScribe
    torch.set_num_threads(4)
    if device=='cuda' and not torch.cuda.is_available():raise ValueError('CUDA unavailable; explicitly choose CPU for a separately recorded run')
    load=time.perf_counter();model=MolScribe(str(checkpoint),device=torch.device(device),num_workers=1)
    if device=='cuda':torch.cuda.synchronize()
    load_seconds=time.perf_counter()-load
    result={'schema':1,'device':device,'torch':torch.__version__,'cuda':torch.version.cuda,
      'gpu':torch.cuda.get_device_name(0) if device=='cuda' else None,'checkpoint_sha256':spec['checkpoint_sha256'],
      'manifest_sha256':sha(manifest),'model_load_seconds':round(load_seconds,4),'cases':[],
      'external_AI_calls':0,'local_neural_model':True,'LLM_calls':0,'scientific_acceptance':False}
    write(output/'result.json',result)
    for case in cases:
        clock=time.perf_counter();row={'case_id':case['case_id'],'image_sha256':case['image_sha256']}
        try:
            # PIL handles Windows Unicode paths; cv2.imread does not on some versions.
            with Image.open(safe(case['image'])) as im:array=np.array(im.convert('RGB'))
            prediction=model.predict_image(array,return_atoms_bonds=True,return_confidence=True)
            if device=='cuda':torch.cuda.synchronize()
            row['inference_seconds']=round(time.perf_counter()-clock,4)
            row['prediction']=prediction;row['screen']=chemical_graph(prediction,case.get('elements'))
            if row['screen']['graph'] is not None:
                graph_path=output/(case['case_id']+'_graph.json');write(graph_path,row['screen']['graph']);row['graph_path']=str(graph_path);row['graph_sha256']=sha(graph_path)
        except Exception as exc:row.update(status='failed',error=str(exc),traceback=traceback.format_exc())
        row['total_seconds']=round(time.perf_counter()-clock,4);result['cases'].append(row);write(output/'result.json',result)
        print(json.dumps({'case_id':case['case_id'],'status':row.get('screen',{}).get('status',row.get('status')),'seconds':row['total_seconds']},ensure_ascii=False),flush=True)
    if device=='cuda':result['peak_GPU_allocated_MiB']=round(torch.cuda.max_memory_allocated()/1024**2,1)
    result['wall_seconds']=round(time.perf_counter()-start,4);result['input_hashes_unchanged']=all(sha(c['image'])==c['image_sha256'] for c in cases)
    write(output/'result.json',result);write(output/'predictions_seal.json',{'result_sha256':sha(output/'result.json'),'image_manifest_sha256':sha(manifest),'reference_answers_read':False})
    return result
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',required=True);p.add_argument('--checkpoint',required=True);p.add_argument('--output',required=True);p.add_argument('--device',choices=['cuda','cpu'],default='cuda');a=p.parse_args()
    result=run(a.manifest,a.checkpoint,a.output,a.device);print(json.dumps({k:v for k,v in result.items() if k!='cases'},ensure_ascii=False))
if __name__=='__main__':main()
