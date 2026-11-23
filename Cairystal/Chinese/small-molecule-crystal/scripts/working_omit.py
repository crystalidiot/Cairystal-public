"""Select one documented reflection set and prepare a separately validated working CIF."""
import math
from collections import Counter
from pathlib import Path
import shutil

import gemmi
from crystal_runtime import REFLECTION_TAGS, paired_bundle, sha, write_json
from reflection_omit_trial import validate_list


def active_indices(path):
    block = gemmi.cif.read_file(str(path)).sole_block()
    return {tuple(map(int, list(r)[:3])) for r in block.find(REFLECTION_TAGS) if r[6].lower() != 'x'}


def checked_selection(control, trial, comparison, hkls, folder):
    wanted = {tuple(h) for h in validate_list(hkls)}
    if not trial['source_unchanged'] or trial['native_gate']['review_reasons']:
        raise ValueError('Source or convergence needs review')
    before = control['comparison_context']
    after = dict(trial['comparison_context'])
    cards = after['frozen_controls']
    omit = [r for r in cards if r[0]=='OMIT' and len(r)==4]
    if {tuple(map(int,r[1:])) for r in omit} != wanted or len(omit)!=len(wanted):
        raise ValueError('Applied OMIT cards differ from the fixed list')
    after['frozen_controls'] = [r for r in cards if r not in omit]
    if before!=after:
        raise ValueError('Controls, weights, elements or source HKL differ beyond the fixed list')
    allowed = {'reflection_count_changed','reflection_weight_temperature_or_setting_comparison_unverified'}
    # An unchanged chemical concern is still a concern: do not adopt OMIT to hide it.
    from model_priority import assessment
    chemical=assessment(comparison)
    if chemical['status'] in {'needs_review','contradicted'}:
        raise ValueError('Chemical model review precedes OMIT adoption: '+str(chemical))
    if any((record.get('restraint_tension') or {}).get('needs_review') or
           any(r['absolute_error_over_sigma']>=5 for r in (record.get('restraint_tension') or {}).get('listed_geometry',[]))
           for record in (control,trial)):
        raise ValueError('Resolve or explicitly review geometric restraint conflicts before automatic OMIT adoption')
    unexpected=set(comparison['flags'])-allowed
    if unexpected:
        raise ValueError('Trial needs review: '+', '.join(sorted(unexpected)))
    if trial['parameters']!=control['parameters'] or trial['restraints']!=control['restraints']:
        raise ValueError('Model size or restraint count changed')
    def alerts(rows):
        return Counter((str(a['code']),a['level']) for a in rows if a['level'] in 'AB')
    base_alerts,remaining=alerts(control['AB']),alerts(trial['AB'])
    if remaining-base_alerts or not any(code in {'919','934'} for code,level in base_alerts-remaining):
        raise ValueError('The target alert did not improve, or a new A/B appeared')
    first=folder/control['name']/'native'
    second=folder/trial['name']/'native'
    before_set=active_indices(first/'case.fcf')
    after_set=active_indices(second/'case.fcf')
    if before_set-after_set!=wanted or after_set-before_set:
        raise ValueError('Fitted FCF indices changed beyond the fixed list')
    if control['metrics']['unique']-trial['metrics']['unique']!=len(wanted):
        raise ValueError('Native used-reflection count differs from fixed list')
    def sites(directory):
        from audit_occupancy import audit
        data=audit(directory/'case.res',gemmi)
        return {a['label']:a for a in data['atoms'] if a['element'].upper() not in {'H','D'}}
    original,current=sites(first),sites(second)
    if original.keys()!=current.keys():
        raise ValueError('The heavy atom list changed')
    block=gemmi.cif.read_file(str(first/'case.cif')).sole_block()
    cell=gemmi.UnitCell(*(gemmi.cif.as_number(block.find_value('_cell_'+tag)) for tag in
                          ('length_a','length_b','length_c','angle_alpha','angle_beta','angle_gamma')))
    largest_shift=max(cell.find_nearest_pbc_image(gemmi.Fractional(*original[k]['xyz']),
                      gemmi.Fractional(*a['xyz']),0).dist() for k,a in current.items())
    largest_occ=max(abs(original[k]['inferred_cif_occupancy']-a['inferred_cif_occupancy']) for k,a in current.items())
    if largest_shift>.1 or largest_occ>.02:
        raise ValueError('Heavy-atom coordinates or occupancies changed materially')
    # Report the fitted fraction separately from the CIF completeness values.
    fraction=len(wanted)/len(before_set)
    if fraction>.005:
        raise ValueError('Fixed list exceeds 0.5% of active unique reflections')
    completeness={}
    for label in ('theta_full','theta_max'):
        tag='_diffrn_measured_fraction_'+label
        values=[gemmi.cif.as_number(gemmi.cif.read_file(str(d/'case.cif')).sole_block().find_value(tag) or '?') for d in (first,second)]
        if not all(math.isfinite(v) and 0<=v<=1 for v in values) or values[0]-values[1]>.00500001:
            raise ValueError('Completeness unavailable or loss exceeds 0.5 percentage point: '+label)
        completeness[label]=values
    return {'selected':True,'name':trial['name'],'native':str(second),'hkls':hkls,
            'raw_hkl_sha256':before['hkl_sha256'],'used_reflections':[len(before_set),len(after_set)],
            'excluded_fraction':fraction,'completeness':completeness,'existing_restraint_conflicts':False,
            'max_heavy_atom_shift_A':largest_shift,'max_occupancy_change':largest_occ,'candidate_AB':trial['AB'],
            'weighted_evidence':next(e['reflection_omit']['weighted_evidence'] for e in trial['edits'] if 'reflection_omit' in e)}


def select(trials, comparisons, plans, packet, folder):
    options=[p for p in plans if p.get('reflection_omit')]
    if len(plans)!=1 or len(options)!=1:
        return {'selected':False,'reason':'Competing hypotheses or multiple reflection sets'}
    if not any(str(a['code']) in {'919','934'} for a in packet['AB_alerts']):
        return {'selected':False,'reason':'No specific PLAT919/934 alert'}
    trial=next(t for t in trials if t['name']==options[0]['name'])
    if trial['status']!='completed':
        return {'selected':False,'reason':'The reflection trial did not complete'}
    try:
        return checked_selection(trials[0],trial,comparisons[0],options[0]['reflection_omit']['hkls'],folder)
    except (ValueError,KeyError,OSError) as exc:
        return {'selected':False,'reason':str(exc)}


def notes(selection):
    points=', '.join('('+', '.join(map(str,row['hkl']))+f'; {row["delta_over_sigmaW"]:+.2f})' for row in selection['weighted_evidence'])
    n,m=selection['used_reflections']
    return {
        'zh':f'本次工作模型按 |Iobs−Icalc| > 10σW 排除了 {len(selection["hkls"])} 个反射。各组依次给出 h、k、l 和排除前的有符号加权偏差 {points}。参与精修的反射由 {n} 个变为 {m} 个。原始 HKL 和全数据对照已保留。异常的仪器原因尚未确定。',
        'en':f'The working refinement excluded {len(selection["hkls"])} reflections using the criterion |Iobs-Icalc| > 10 sigmaW. The indices and signed standardized residuals before exclusion (h,k,l; residual) were {points}. The number of fitted reflections changed from {n} to {m}. The original HKL and all-data control were retained. The instrumental origin of the discrepancies is undetermined.'}


def prepare(folder, baseline, selection):
    from routine_finish import carry_metadata, freeze_for_validation
    from atom_labels import sort_cif
    from cif_text_preflight import encode_narratives
    from routine_consistency import require_consistency
    folder.mkdir()
    source=Path(selection['native'])
    if sha(source/'case.hkl')!=sha(baseline/'model.hkl') or sha(source/'case.hkl')!=selection['raw_hkl_sha256']:
        raise ValueError('Candidate measured HKL differs from the selected source')
    staging=folder/'selected'
    staging.mkdir()
    for ext in ('ins','res','lst','hkl','cif','fcf'):
        shutil.copy2(source/('case.'+ext),staging/('model.'+ext))
    cif=staging/'model.cif'
    carry_metadata(baseline/'model.cif',cif,0)
    doc=gemmi.cif.read_file(str(cif))
    b=doc.sole_block()
    tag='_publ_section_exptl_refinement'
    prior=gemmi.cif.as_string(b.find_value(tag) or '?')
    narrative=notes(selection)['en']
    if prior and prior not in {'?','.'}:
        narrative+='\nFull-data baseline history:\n'+prior
    b.set_pair(tag,gemmi.cif.quote(narrative))
    doc.write_file(str(cif))
    encode_narratives(cif,folder/'text_audit.json')
    sort_cif(cif)
    audit=paired_bundle(staging,'model')
    require_consistency(audit['routine_checks'])
    frozen=folder/'frozen'
    freeze_for_validation(audit,frozen,folder/'credit.json')
    labels=baseline/'atom_label_map.json'
    if labels.is_file():
        shutil.copy2(labels,frozen/labels.name)
    write_json(folder/'selection.json',selection)
    return frozen,audit
