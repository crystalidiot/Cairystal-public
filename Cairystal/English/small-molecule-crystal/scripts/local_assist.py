"""Review bridge for local recognition; does not accept a crystal or bypass validation."""
import argparse,json,subprocess,sys,hashlib
from pathlib import Path
from molscribe_local import sha,safe,write,chemical_graph

def load(p):return json.loads(safe(p).read_text(encoding='utf-8-sig'))

def verify_reviewed_graph(graph_path):
    graph_path=safe(graph_path);graph=load(graph_path)
    if not graph.get('local_recognition') and not str(graph.get('source','')).startswith('Local MolScribe'):return
    receipt=load(graph_path.parent/'recognition_review.json')
    if receipt.get('decision') not in {'reviewed_chemical_prior','automatically_screened_chemical_prior'} or not receipt.get('reviewer','').strip() or not receipt.get('basis','').strip():raise ValueError('Recognition review is incomplete')
    if receipt['decision']=='automatically_screened_chemical_prior':
        from diagram_assist import validate_analysis
        if sha(safe(receipt['automatic_analysis']))!=receipt['automatic_analysis_sha256']:raise ValueError('Automatic recognition analysis changed')
        _,row,_,_=validate_analysis(receipt['automatic_analysis'],receipt['case_id'])
        if row['graph_sha256']!=sha(graph_path):raise ValueError('Graph differs from the automatically screened candidate')
    if sha(graph_path)!=receipt['approved_graph_sha256']:raise ValueError('Reviewed graph hash changed')
    for name in ['source_image','raw_prediction_record']:
        if sha(safe(receipt[name]))!=receipt[name+'_sha256']:raise ValueError('Recognition evidence changed: '+name)
    if receipt.get('correction_file') and sha(safe(receipt['correction_file']))!=receipt['correction_file_sha256']:raise ValueError('Correction evidence changed')

def review(predictions,case_id,output,reviewer,basis,correction=None):
    if not reviewer.strip() or len(basis.strip())<20:raise ValueError('Named reviewer and actual image/chemistry review basis required')
    predictions=safe(predictions);output=safe(output)
    if output.exists():raise ValueError('Use a new review directory')
    record=predictions/'result.json';seal=load(predictions/'predictions_seal.json')
    if sha(record)!=seal['result_sha256']:raise ValueError('Raw predictions changed')
    result=load(record);inputs=load(predictions/'input_used.json')
    case=next(c for c in result['cases'] if c['case_id']==case_id);source=next(c for c in inputs['cases'] if c['case_id']==case_id)
    if sha(safe(source['image']))!=source['image_sha256']:raise ValueError('Source image changed')
    prediction=dict(case['prediction']);correction_path=None
    if correction:
        correction_path=safe(correction);patch=load(correction_path)
        if set(patch)!={'reviewed_smiles','reason'} or not patch['reason'].strip():raise ValueError('Explicit corrected SMILES and reason required')
        prediction['smiles']=patch['reviewed_smiles']
    screen=chemical_graph(prediction,source.get('elements'))
    if screen['graph'] is None:raise ValueError('No valid graph')
    unsupported=[i for i in screen['issues'] if any(w in i for w in ['Isotope','R-group','Explicit H','Radical','stereochemistry','Unsupported bond','outside the explicitly'])]
    if unsupported:raise ValueError('Dedicated downstream handling required: '+'; '.join(unsupported))
    graph=screen['graph'];graph['local_recognition']=True
    graph['source']='Image-derived chemical prior reviewed for elements, bond orders, charges, protonation and component multiplicity. Not a validated crystal.'
    output.mkdir(parents=True);path=output/'chemical_graph.json';write(path,graph)
    receipt={'schema':1,'decision':'reviewed_chemical_prior','reviewer':reviewer,'basis':basis,
      'case_id':case_id,'source_image':source['image'],'source_image_sha256':source['image_sha256'],
      'raw_prediction_record':str(record),'raw_prediction_record_sha256':sha(record),
      'raw_smiles':case['prediction']['smiles'],'approved_smiles':prediction['smiles'],
      'corrected':bool(correction),'approved_graph_sha256':sha(path),'remaining_screen_findings':screen['issues'],
      'correction_file':str(correction_path) if correction_path else None,
      'correction_file_sha256':sha(correction_path) if correction_path else None,
      'scientific_structure_acceptance':False,'mandatory_followup':'Fresh solution/refinement, difference map/ADP/occupancy checks, local AB, official IUCr and bilingual Word.'}
    write(output/'recognition_review.json',receipt);verify_reviewed_graph(path)
    return {'graph':str(path),'review':str(output/'recognition_review.json'),'corrected':bool(correction)}

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('review');a.add_argument('--predictions',required=True);a.add_argument('--case-id',required=True);a.add_argument('--output',required=True);a.add_argument('--reviewer',required=True);a.add_argument('--basis',required=True);a.add_argument('--correction')
    a=sub.add_parser('verify');a.add_argument('--graph',required=True)
    a=p.parse_args()
    if a.command=='verify':verify_reviewed_graph(a.graph);print('verified')
    else:print(json.dumps(review(a.predictions,a.case_id,a.output,a.reviewer,a.basis,a.correction),ensure_ascii=False))
if __name__=='__main__':main()
