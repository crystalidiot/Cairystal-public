"""Run an explicitly prepared SHELX candidate in a new directory; never repair it automatically."""
import argparse, json, shutil, sys
from copy import deepcopy
from pathlib import Path
from crystal_runtime import regular,new_directory,sha,write_json,run_command,check_stem,check_instructions,utc_now


# One tiny format report for the current reflection file. Never cache a model
# or raw diffraction bytes. Every native stage hashes its own working copy.
_last_hkl_check = None


def staged_hkl_check(source, working, expected_digest):
    from inspect_case import reflection_stats
    global _last_hkl_check
    key = (source.resolve(), expected_digest)
    previous = _last_hkl_check
    if previous is not None and previous[0] == key:
        if sha(working) != expected_digest:
            raise ValueError('Staged HKL differs from the recorded input')
        return deepcopy(previous[1]), True
    stats = reflection_stats(working)
    if stats['sha256'].lower() != expected_digest:
        raise ValueError('Staged HKL differs from the recorded input')
    _last_hkl_check = (key, deepcopy(stats))
    return stats, False

def run(args):
    executable=regular(args.executable);ins=regular(args.ins);hkl=regular(args.hkl);stem=check_stem(args.stem)
    if executable.stem.lower() not in {'shelxl','shelxt','shelxd'}:raise ValueError('Only explicitly supplied SHELXL/SHELXT/SHELXD executables supported')
    fab=regular(args.fab) if getattr(args,'fab',None) else None
    hashes={str(p):sha(p) for p in [ins,hkl,executable]+([fab] if fab else [])};out=new_directory(args.output)
    record={'started_at':utc_now(),'reason':args.reason,'inputs':hashes,'model_changes_automatic':False}
    write_json(out/'attempt.json',record)
    try:
        text=ins.read_text(encoding='latin1')
        lines=check_instructions(text)
        masked=any(r[0].upper()=='ABIN' for r in lines)
        if masked != bool(fab):raise ValueError('Active ABIN requires an explicit paired --fab; unmasked models cannot consume FAB')
        if fab:
            if executable.stem.lower()!='shelxl':raise ValueError('ABIN/FAB is a refinement input, not a solution input')
            from squeeze_bundle import parse_fab
            parse_fab(fab.read_text('latin1'))
        from shelx_input_preflight import validate_native_input
        record['input_preflight']=validate_native_input(text)
        working_hkl=out/f'{stem}.hkl'
        shutil.copy2(hkl,working_hkl)
        record['hkl_preflight'],record['hkl_format_reused']=staged_hkl_check(hkl,working_hkl,hashes[str(hkl)])
        if not record['hkl_preflight']['standard_layout_recognized']:raise ValueError('Unrecognized HKLF 4 layout; original reflections preserved')
        shutil.copy2(ins,out/f'{stem}.ins')
        if fab:shutil.copy2(fab,out/f'{stem}.fab')
        command=[executable,stem]
        if getattr(args,'threads',None) is not None or getattr(args,'matrix_parameters',None) is not None:
            if executable.stem.lower()!='shelxl':raise ValueError('Resource overrides on this entry are for SHELXL only')
            if getattr(args,'threads',None) is not None:command.append('-t'+str(args.threads))
            if getattr(args,'matrix_parameters',None) is not None:command.append('-b'+str(args.matrix_parameters))
        record.update(run_command(command,out,out/'process.log',args.timeout))
        if executable.stem.lower()=='shelxl':
            from refinement_gate import assess
            record['gate']=assess(out,stem)
        else:
            record['candidate_outputs']=[p.name for p in out.glob(stem+'*.res') if p.stat().st_size>0]
        record['inputs_unchanged']=all(sha(p)==h for p,h in hashes.items())
        record['outputs']={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='attempt.json'}
        record['success']=bool(record['returncode']==0 and record['process_state']=='finished' and record['inputs_unchanged'] and record.get('gate',{}).get('execution_complete',True))
        if executable.stem.lower()!='shelxl' and not record['candidate_outputs']:record['success']=False
        record['scientific_acceptance']='not_established'
    except Exception as exc:
        record['success']=False;record['error']=str(exc)
    record['finished_at']=utc_now();write_json(out/'attempt.json',record)
    print(json.dumps({'output':str(out),'success':record['success'],'full_delivery_complete':False,'completion_entry':'complete_candidate.py after current-model review','elapsed_s':record.get('elapsed_s'),'metrics':record.get('gate',{}).get('metrics'),'review':record.get('gate',{}).get('review_reasons'),'error':record.get('error')},ensure_ascii=False))
    return 0 if record['success'] else 1

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['executable','ins','hkl','output','reason']:p.add_argument('--'+key,required=True)
    p.add_argument('--fab');p.add_argument('--stem',default='model');p.add_argument('--timeout',type=float,default=600)
    p.add_argument('--threads',type=int);p.add_argument('--matrix-parameters',type=int)
    sys.exit(run(p.parse_args()))
