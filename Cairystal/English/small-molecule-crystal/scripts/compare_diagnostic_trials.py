"""Compare explicit trial records without selecting or accepting a structure.

Use a newly run unchanged continuation as control. Preserve every AB occurrence.
Output is compact evidence, not a solver, diagnosis, or final-model decision.
"""
from pathlib import Path
from collections import defaultdict
import argparse,hashlib,json,re

METADATA_CODES={'035','183','184','185','196','197','198','699','881'}

def alert_key(a):
 text=' '.join(str(a['text']).split())
 # Only the documented numeric payload of atom-specific ADP alerts is masked.
 # Labels (including PART suffixes), symmetry context and unknown wording stay.
 if str(a['code']) in {'213','214','234'} and a.get('atom_labels'):
  text=re.sub(r'(\.{3,}\s*)[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?',r'\1<value>',text,count=1)
 context={k:a[k] for k in ('part','residue','symmetry','symmetry_code','atom_labels') if k in a}
 return (str(a['code']),str(a['level']),a.get('type'),text,json.dumps(context,sort_keys=True))

def changes(before,after):
 b=defaultdict(list);a=defaultdict(list)
 for alert in before:b[alert_key(alert)].append(alert)
 for alert in after:a[alert_key(alert)].append(alert)
 result={'removed':[],'added':[],'unchanged':[],'value_changed':[]}
 for key in dict.fromkeys([*b,*a]):
  old=list(b[key]);new=list(a[key])
  # Pair exact occurrences first, so duplicates with shifted values retain counts.
  for item in list(old):
   if item in new:result['unchanged'].append(item);old.remove(item);new.remove(item)
  while old and new:
   prior=old.pop(0);current=new.pop(0)
   result['unchanged'].append(current)
   result['value_changed'].append({'before':prior,'after':current})
  result['removed'].extend(old);result['added'].extend(new)
 return result

def counts(alerts):
 if alerts is None:return None
 return {g:{level:sum(a['level']==level and ((str(a['code']) in METADATA_CODES)==(g=='metadata')) for a in alerts) for level in 'AB'} for g in ['metadata','other']}

def compare(control,trial):
 out={k:trial.get(k) for k in ['name','kind','status','hypothesis','evidence','plan','diagnostic','elapsed_s','errors','source_unchanged','model_sha256','chemical_review']}
 alerts=trial.get('AB') if trial.get('status')=='completed' else None
 out.update(model_adopted=False,classification='needs_review',metrics=trial.get('metrics'),AB=alerts,AB_counts=counts(alerts),flags=[])
 if trial.get('status')!='completed':
  out['classification']={'completed_map':'map_only','skipped_identical_configuration':'identical_configuration_not_rerun'}.get(trial.get('status'),'execution_failed')
  return out
 if control.get('status')!='completed':raise ValueError('Completed contemporaneous control required')
 if trial.get('diagnostic') and any('split_fragment' in edit for edit in trial.get('edits',[])):
  from disorder_bond_review import trial_review
  out['bond_review']=trial_review(Path(trial['diagnostic']).parent/'paired','case')
  if out['bond_review']['findings']:out['flags'].append('short_bond_in_disorder_component')
  if out['bond_review']['status']=='unavailable':out['flags'].append('disorder_bond_review_unavailable')
 context_before=control.get('comparison_context');context_after=trial.get('comparison_context')
 out['comparison_context_verified']=bool(context_before and context_after and context_before==context_after)
 if not out['comparison_context_verified']:out['flags'].append('reflection_weight_temperature_or_setting_comparison_unverified')
 before=control.get('metrics',{});after=trial.get('metrics',{});deltas={}
 for key in ['R1_observed','wR2','GooF','NPD_atoms','last_abs_max_shift_esd','unique']:
  a=before.get(key);b=after.get(key);deltas[key]={'control':a,'trial':b,'delta':None if a is None or b is None else b-a}
 if not isinstance(alerts,list) or not isinstance(control.get('AB'),list):
  out.update(comparison=deltas,AB_changes=None)
  out['flags'].append('validated_AB_evidence_missing');out['classification']='execution_failed';return out
 out.update(comparison=deltas,AB_changes=changes(control.get('AB',[]),trial.get('AB',[])),
   density={'control':control.get('difference_density'),'trial':trial.get('difference_density')},
   parameters={'control':control.get('parameters'),'trial':trial.get('parameters')},
   restraints={'control':control.get('restraints'),'trial':trial.get('restraints')},
   geometry=trial.get('geometry_results',[]),occupancy_warnings=trial.get('occupancy_warnings',[]))
 if trial.get('same_fitted_data') is False:out['flags'].append('explicit_resolution_sensitivity_different_fitted_data')
 if after.get('unique')!=before.get('unique'):out['flags'].append('reflection_count_changed')
 if after.get('NPD_atoms') not in (0,None):out['flags'].append('non_positive_definite_ADP')
 shift=after.get('last_abs_max_shift_esd')
 if shift is None or shift>.01:out['flags'].append('convergence_requires_review')
 if any(not g['within_declared_range'] for g in out['geometry']):out['flags'].append('geometry_outside_declared_hypothesis')
 dr=deltas['R1_observed']['delta']
 if dr is not None and dr>.001:out['flags'].append('R1_increased_more_than_screening_margin')
 if out['occupancy_warnings']:out['flags'].append('occupancy_or_UNIT_accounting_review')
 out['restraint_tension']=trial.get('restraint_tension')
 out['hydrogen_geometry']=trial.get('hydrogen_geometry')
 if out['hydrogen_geometry'] and any(h['very_short_contacts_below_0_8_A'] for h in out['hydrogen_geometry']['after']['hydrogens']):out['flags'].append('new_H_geometry_requires_clash_review')
 if out['restraint_tension'] and out['restraint_tension'].get('needs_review'):
  out['flags'].append('geometry_restraints_conflict_with_refined_model')
 if not out['restraint_tension'] or out['restraint_tension'].get('needs_review') is None:
  out['restraint_geometry_assessment']='not_established_by_listing'
 else:out['restraint_geometry_assessment']='screened_listed_conflicts_only'
 out['ADP_summary']={'control':control.get('ADP_summary'),'trial':trial.get('ADP_summary')}
 bd=control.get('difference_density') or {};ad=trial.get('difference_density') or {}
 for side in ['max','min']:
  old=bd.get(side);new=ad.get(side)
  if old is not None and new is not None and abs(new)-abs(old)>max(.05,.2*abs(old)):
   out['flags'].append('residual_'+side+'_worsened')
 p0=control.get('parameters');p1=trial.get('parameters');n=after.get('unique')
 out['model_complexity']={'parameter_delta':p1-p0 if p0 is not None and p1 is not None else None,
  'observations_per_parameter':n/p1 if n is not None and p1 else None,
  'note':'Added parameters and restraints are reported; lower R alone does not justify a split. No significance test or automatic winner claimed.'}
 new_model_ab=[a for a in out['AB_changes']['added'] if str(a['code']) not in METADATA_CODES]
 if new_model_ab:out['flags'].append('new_nonmetadata_AB')
 gone_model_ab=[a for a in out['AB_changes']['removed'] if str(a['code']) not in METADATA_CODES]
 if out['flags']:out['classification']='not_supported_without_further_review'
 elif gone_model_ab:out['classification']='alert_reduced_scientific_review_required'
 elif trial.get('kind')=='baseline':out['classification']='unchanged_continuation_control'
 else:out['classification']='no_demonstrated_alert_improvement'
 out['policy']='Screening flags are not proof of a wrong model; no final model is accepted automatically. Metadata alerts remain retained.'
 return out

def run(control_file,result_files,output,chemical_reviews=None):
 control=json.loads(Path(control_file).read_text(encoding='utf-8'));rows=[];inputs={}
 reviews=json.loads(Path(chemical_reviews).read_text(encoding='utf-8-sig')) if chemical_reviews else {}
 if not isinstance(reviews,dict):raise ValueError('Chemical reviews must map trial names to evidence records')
 matched=set()
 if chemical_reviews:inputs[str(chemical_reviews)]=hashlib.sha256(Path(chemical_reviews).read_bytes()).hexdigest()
 for file in result_files:
  p=Path(file);inputs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();data=json.loads(p.read_text(encoding='utf-8'))
  trials=data.get('cases',[data])
  for trial in trials:
   if trial.get('name') in reviews:
    from model_priority import bind_review
    trial=bind_review(trial,reviews[trial['name']]);matched.add(trial['name'])
   rows.append(compare(control,trial))
 if set(reviews)-matched:raise ValueError('Chemical review names did not match supplied trials: '+str(sorted(set(reviews)-matched)))
 from ab_auto import rank_rows
 rows=rank_rows(rows)
 out={'schema':1,'control':str(control_file),'input_hashes':inputs,'cases':rows,'model_adopted':False}
 p=Path(output)
 if p.exists():raise FileExistsError(str(p))
 p.write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8');return out

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--control',required=True);p.add_argument('--results',nargs='+',required=True);p.add_argument('--output',required=True);p.add_argument('--chemical-reviews')
 a=p.parse_args();v=run(a.control,a.results,a.output,a.chemical_reviews);print(json.dumps({'trials':len(v['cases']),'output':a.output},ensure_ascii=False))
