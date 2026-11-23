"""Independent population starts for an existing complementary two-PART model.

This tests a supplied disorder hypothesis, not whether disorder exists. Supported
groups are balanced, full general sites sharing one SOF-only FVAR.
"""
import argparse,collections,json,math,re
from pathlib import Path
import gemmi
from structure_diagnostics import res_records,newjson
from audit_occupancy import audit as occupancy_audit

def context(base,index):
    if type(index)!=int or not 2<=index<=99:raise ValueError('Explicit FVAR index 2..99 required')
    path=Path(base)/'case.res';parsed=res_records(path)
    values=[float(x) for row in parsed['rows'] if row[0].upper()=='FVAR' for x in row[1:]]
    if index>len(values) or not all(math.isfinite(x) for x in values):raise ValueError('Missing or invalid FVAR')
    if any(r[0].upper() in {'SUMP','SWAT','ABIN','TWIN','BASF'} or r[0].startswith('+') for r in parsed['rows']):raise ValueError('Coupled/global population controls require explicit specialist trials')
    if any((r[0].upper()=='PART' and len(r)>2) or (r[0].upper()=='AFIX' and len(r)>3) for r in parsed['rows']):raise ValueError('PART/AFIX population overrides need an explicit accounting route')
    def ref(v):return int(abs(v)//10) if abs(v)>=15 else None
    selected=[]
    for atom in parsed['atoms']:
        # A variable used in coordinates or ADPs is not an occupancy-only trial.
        if any(ref(float(v))==index for v in atom['row'][2:5]+atom['row'][6:]):raise ValueError('Target FVAR also controls a coordinate or ADP')
        if ref(atom['encoded_sof'])==index:
            if abs(abs(atom['encoded_sof'])-(index*10+1))>1e-7 or atom['part']<=0:raise ValueError('Only full general complementary SOF +/- (10*n+1) in positive PARTs supported')
            selected.append(atom)
    if not selected:raise ValueError('FVAR has no atom SOF references')
    if not any(a['element'].upper()!='H' for a in selected):raise ValueError('At least one non-H site in each population group required')
    if len({a['label'].upper() for a in parsed['atoms']})!=len(parsed['atoms']):raise ValueError('Unique atom labels required for cross-run comparison')
    positive=[a for a in selected if a['encoded_sof']>0];negative=[a for a in selected if a['encoded_sof']<0]
    if not positive or not negative:raise ValueError('Both complementary components required')
    pa={a['part'] for a in positive};pb={a['part'] for a in negative}
    if len(pa)!=1 or len(pb)!=1 or pa==pb:raise ValueError('Two distinct PARTs required')
    if collections.Counter(a['element'] for a in positive)!=collections.Counter(a['element'] for a in negative):raise ValueError('Components have unequal element counts; UNIT would depend on population')
    account=occupancy_audit(path,gemmi);labels={a['label'].upper() for a in selected}
    for a in account['atoms']:
        if a['label'].upper() in labels and a['geometric_site_multiplicity']!=a['general_multiplicity']:raise ValueError('Special-position population needs a separate route')
    return dict(index=index,current_value=values[index-1],values=values,
        atoms=[a['label'] for a in selected],heavy_atoms=[a['label'] for a in selected if a['element'].upper()!='H'],parts=[next(iter(pa)),next(iter(pb))])

def edit(base,request):
    if set(request)!={'fvar_index','value','basis'} or not isinstance(request['basis'],str) or not request['basis'].strip():raise ValueError('Explicit index, start value and basis required')
    value=request['value']
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not .1<=value<=.9:raise ValueError('Interior population start in 0.1..0.9 required')
    c=context(base,request['fvar_index']);source=(Path(base)/'case.res').read_text('latin1')
    # Normalise FVAR cards only. Leave all atom records, restraints and HKL intact.
    from audit_occupancy import logical_lines
    values=list(c['values']);values[c['index']-1]=value;out=[];inserted=False;ended=False
    for line in logical_lines(source):
        fields=line.split();key=fields[0].upper()
        if not ended and key=='FVAR':
            if not inserted:out.append('FVAR '+' '.join(f'{v:.9g}' for v in values));inserted=True
            continue
        out.append(line)
        if key=='END':ended=True
    return '\n'.join(out)+'\n',[dict(population_start=dict(c,new_value=value,basis=request['basis']),raw_HKL_changed=False)]

def summarize(results,output,index):
    rows=[];populations=[];coordinates=[];reasons=[];out=Path(output)
    for result in results:
        entry=dict(name=result['name'],status=result['status'],final_population=None,numerically_converged=False)
        if result['status']=='completed':
            try:
                paired=out/result['name']/'paired';c=context(paired,index)
                b=gemmi.cif.read_file(str(paired/'case.cif')).sole_block()
                cell=gemmi.UnitCell(*[gemmi.cif.as_number(b.find_value('_cell_'+x)) for x in ['length_a','length_b','length_c','angle_alpha','angle_beta','angle_gamma']])
                amap={gemmi.cif.as_string(r[0]).upper():[gemmi.cif.as_number(x) for x in list(r)[1:]] for r in b.find(['_atom_site_label','_atom_site_fract_x','_atom_site_fract_y','_atom_site_fract_z'])}
                xyz={n.upper():amap[n.upper()] for n in c['heavy_atoms']}
                if any(not math.isfinite(v) for x in xyz.values() for v in x):raise ValueError('Unknown coordinate')
                entry.update(final_population=c['current_value'],numerically_converged=result.get('gate')=='numerically_converged_requires_chemical_validation',metrics=result.get('metrics'),AB=result.get('AB'))
                populations.append(c['current_value']);coordinates.append((cell,xyz))
            except Exception as exc:entry['error']=str(exc);reasons.append('incomplete_final_population_or_geometry')
        else:reasons.append('trial_failed_or_skipped')
        if not entry['numerically_converged']:reasons.append('not_all_trials_numerically_converged')
        rows.append(entry)
    spread=max(populations)-min(populations) if len(populations)==len(results) and len(results)>=3 else None
    rms=[]
    for i,(cell,a) in enumerate(coordinates):
        for _,b in coordinates[i+1:]:
            if set(a)!=set(b):reasons.append('atom_identity_changed');continue
            rms.append(math.sqrt(sum(cell.find_nearest_pbc_image(gemmi.Fractional(*a[n]),gemmi.Fractional(*b[n]),0).dist()**2 for n in a)/len(a)))
    max_rms=max(rms) if rms else None
    if any(p<.05 or p>.95 for p in populations):reasons.append('population_at_boundary_or_outside_physical_range')
    if spread is None or spread>.02:reasons.append('population_start_dependence_or_incomplete_test')
    if max_rms is None or max_rms>.1:reasons.append('coordinate_start_dependence_or_incomplete_test')
    return dict(status='screen_stable_requires_model_review' if not reasons else 'needs_review',trials=rows,
        population_range=spread,max_same_label_pairwise_RMSD_A=max_rms,screen_thresholds={'population_range':.02,'RMSD_A':.1},reasons=sorted(set(reasons)),
        model_adopted=False,limitations=['Stability does not prove the disorder model is correct or uniquely determined.',
        'Only lattice translations and the same atom labels are compared; a swapped component is flagged for review, not automatically relabelled.',
        'Same data, weights, atom positions and restraints at start; only the selected occupancy FVAR differs.'])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',required=True);p.add_argument('--fvar-index',required=True,type=int);p.add_argument('--output',required=True)
    a=p.parse_args();v=context(a.directory,a.fvar_index);v.update(status='supported_existing_population_group',model_modified=False,next='Use repair-plan occupancy_stability with explicit starts and evidence.');newjson(a.output,v);print(json.dumps(v))
if __name__=='__main__':main()
