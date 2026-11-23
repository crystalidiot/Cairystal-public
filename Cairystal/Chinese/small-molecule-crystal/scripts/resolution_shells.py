"""Read-only equal-1/d^2 shell diagnostics from a paired LIST 4 FCF.

Shell statistics describe available FCF rows, not raw-frame completeness or proof
of bad exposure. No cutoff, merge, reflection rejection or model edit is applied.
"""
import argparse,json,math,statistics,time
from pathlib import Path
import gemmi
from reflection_audit import audit as reflection_audit,row_metrics
from crystal_runtime import REFLECTION_TAGS,sha
from structure_diagnostics import newjson

def summarize(rows):
    active=[r for r in rows if r['status'].lower()!='x']
    signals=[r['Fo2']/r['sigma_Fo2'] for r in active]
    weighted=[r['delta_over_sigmaW'] for r in active if r['delta_over_sigmaW'] is not None]
    denominator=sum(math.sqrt(max(r['Fo2'],0)) for r in active)
    return dict(FCF_rows=len(rows),active_rows=len(active),excluded_rows=len(rows)-len(active),
        mean_I_over_sigma=statistics.mean(signals) if signals else None,
        median_I_over_sigma=statistics.median(signals) if signals else None,
        fraction_I_gt_2sigma=sum(x>2 for x in signals)/len(signals) if signals else None,
        negative_intensity_fraction=sum(x<0 for x in signals)/len(signals) if signals else None,
        signed_weighted_mean=statistics.mean(weighted) if weighted and len(weighted)==len(active) else None,
        weighted_rms=math.sqrt(statistics.mean(x*x for x in weighted)) if weighted and len(weighted)==len(active) else None,
        weighted_gt10_count=sum(abs(x)>10 for x in weighted) if len(weighted)==len(active) and active else None,
        R1_all_available_FCF=sum(abs(math.sqrt(max(r['Fo2'],0))-math.sqrt(r['Fc2'])) for r in active)/denominator if denominator else None,
        theoretical_completeness=None,Rint=None)

def partition(rows,bins=6):
    if type(bins)!=int or not 2<=bins<=20:raise ValueError('bins must be an integer in 2..20')
    if not rows:raise ValueError('No FCF reflection rows')
    q=[1/r['d_A']**2 for r in rows]
    if any(not math.isfinite(v) or v<=0 for v in q):raise ValueError('Invalid reflection resolution')
    low,high=min(q),max(q)
    if high-low<1e-12:
        return [dict(index=1,d_low_resolution_A=1/math.sqrt(low),d_high_resolution_A=1/math.sqrt(high),**summarize(rows))]
    width=(high-low)/bins;groups=[[] for _ in range(bins)]
    for row,value in zip(rows,q):groups[min(bins-1,int((value-low)/width))].append(row)
    return [dict(index=i+1,d_low_resolution_A=1/math.sqrt(low+i*width),d_high_resolution_A=1/math.sqrt(low+(i+1)*width),**summarize(group)) for i,group in enumerate(groups)]

def audit(directory,stem='case',bins=6):
    start=time.perf_counter();e=reflection_audit(directory,stem);files=e['source_files']
    b=gemmi.cif.read_file(files['cif']).sole_block();fb=gemmi.cif.read_file(files['fcf']).sole_block()
    cell=gemmi.UnitCell(*[gemmi.cif.as_number(fb.find_value('_cell_'+t)) for t in ['length_a','length_b','length_c','angle_alpha','angle_beta','angle_gamma']])
    wavelength=gemmi.cif.as_number(b.find_value('_diffrn_radiation_wavelength') or '?')
    wavelength=wavelength if math.isfinite(wavelength) and wavelength>0 else None
    weights=e['weighting']['parameters'];rows=[]
    for r in fb.find(REFLECTION_TAGS):
        row=row_metrics([int(r[i]) for i in range(3)],float(r[4]),float(r[3]),float(r[5]),cell,wavelength,weights)
        row['status']=str(r[6]);rows.append(row)
    result=dict(schema=1,status='evidence_ready',binning='equal width in 1/d^2; low to high angle',
        source_files=files,source_sha256=e['source_sha256'],weighting=e['weighting'],shells=partition(rows,bins),overall=summarize(rows),
        model_modified=False,cutoff_proposed=None,automatic_reflection_rejection=False,
        limitations=['Only available paired FCF rows; missing raw reflections cannot be reconstructed.',
        'Completeness and Rint remain null: merged FCF values are not unmerged measurement statistics.',
        'Shell R1 and reconstructed weight residuals use rounded FCF values; they are not an independent model validation.',
        'Weak high-angle signal alone is not a reason to truncate; compare a justified hypothesis separately.'])
    result['source_unchanged']=e['source_sha256']=={k:sha(v) for k,v in files.items()}
    if not result['source_unchanged']:raise ValueError('Inputs changed during shell audit')
    result['seconds']=round(time.perf_counter()-start,4);return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--directory',required=True);p.add_argument('--stem',default='case');p.add_argument('--bins',type=int,default=6);p.add_argument('--output',required=True)
    a=p.parse_args();v=audit(a.directory,a.stem,a.bins);newjson(a.output,v)
    print(json.dumps({'status':v['status'],'shells':len(v['shells']),'seconds':v['seconds']}))
if __name__=='__main__':main()
