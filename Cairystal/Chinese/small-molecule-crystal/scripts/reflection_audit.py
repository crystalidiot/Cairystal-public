"""Read-only LIST 4 outlier evidence; measured sigma is not SHELXL sigmaW."""
import argparse
import json
import math
from pathlib import Path
import re
import time
import gemmi
from crystal_runtime import paired_bundle,REFLECTION_TAGS,sha
from structure_diagnostics import newjson


def standard_weights(block):
    # Read the weighting formula used to generate the paired CIF, not the suggested
    # next-cycle WGHT at the end of RES. Unknown/extended formula => null sigmaW.
    text=gemmi.cif.as_string(block.find_value('_refine_ls_weighting_details') or "''")
    s=re.sub(r'\s+','',text).lower().replace('\\s','sigma').replace('^2^','^2')
    num=r'([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)'
    match=re.fullmatch(r'w=1/\[sigma\^2\(fo\^2\)\+\('+num+r'p\)\^2\+'+num+r'p\]wherep=\(fo\^2\+2fc\^2\)/3',s)
    if not match:
        return None,text
    a,b=map(float,match.groups())
    return ((a,b) if math.isfinite(a) and math.isfinite(b) and a>=0 and b>=0 else None),text


def row_metrics(hkl,fo,fc,sigma,cell,wavelength,weights):
    if not all(math.isfinite(v) for v in [fo,fc,sigma]) or sigma<=0 or fc<0 or hkl==[0,0,0]:
        raise ValueError('Invalid FCF reflection row')
    d=cell.calculate_d(hkl)
    if not math.isfinite(d) or d<=0:
        raise ValueError('Invalid reciprocal resolution')
    theta=None
    if wavelength is not None and 0<wavelength/(2*d)<=1:
        theta=math.degrees(math.asin(wavelength/(2*d)))
    weighted=None;sigw=None
    if weights is not None:
        a,b=weights;p=(max(0,fo)+2*fc)/3
        sigw=math.sqrt(sigma*sigma+(a*p)**2+b*p)
        weighted=(fo-fc)/sigw
    return dict(hkl=hkl,Fo2=fo,Fc2=fc,sigma_Fo2=sigma,d_A=d,theta_degrees=theta,
                delta_over_sigma=(fo-fc)/sigma,sigmaW=sigw,delta_over_sigmaW=weighted)


def audit(directory,stem='case'):
    start=time.perf_counter();bundle=paired_bundle(directory,stem)
    paths=bundle['files'];b=gemmi.cif.read_file(paths['cif']).sole_block();fb=gemmi.cif.read_file(paths['fcf']).sole_block()
    cell=gemmi.UnitCell(*[float(gemmi.cif.as_number(fb.find_value('_cell_'+t))) for t in ['length_a','length_b','length_c','angle_alpha','angle_beta','angle_gamma']])
    weights,formula=standard_weights(b)
    reasons=[]
    if weights is None:reasons.append('Unrecognised/extended weighting formula; weighted outliers unavailable')
    multiplier=gemmi.cif.as_number(fb.find_value('_shelx_F_squared_multiplier') or '?')
    if multiplier!=1:
        weights=None;reasons.append('FCF squared-intensity multiplier is not explicitly 1; no weight reconstruction')
    if any(line.split()[0].upper() in {'TWIN','BASF','ABIN','SWAT'} for line in Path(paths['res']).read_text('latin1').splitlines() if line.strip()):
        weights=None;reasons.append('Twin/mask or solvent correction requires specialist weighted-factor interpretation')
    value=gemmi.cif.as_number(b.find_value('_diffrn_radiation_wavelength') or '?')
    wavelength=value if math.isfinite(value) and value>0 else None
    rows=[]
    for r in fb.find(REFLECTION_TAGS):
        row=row_metrics([int(r[i]) for i in range(3)],float(r[4]),float(r[3]),float(r[5]),cell,wavelength,weights)
        row['status']=str(r[6]);rows.append(row)
    active=[r for r in rows if r['status']!='x']
    weighted=[r for r in active if r['delta_over_sigmaW'] is not None and abs(r['delta_over_sigmaW'])>10]
    unweighted=[r for r in active if abs(r['delta_over_sigma'])>10]
    low=[r for r in weighted if r['theta_degrees'] is not None and r['theta_degrees']<3 and r['delta_over_sigmaW']<-10]
    ranked=sorted(active,key=lambda r:abs(r['delta_over_sigmaW'] if r['delta_over_sigmaW'] is not None else r['delta_over_sigma']),reverse=True)
    if bundle['source_sha256']!={e:sha(p) for e,p in paths.items()}:
        raise ValueError('Input changed during reflection audit')
    return dict(schema=1,status='evidence_ready' if weights is not None else 'weighted_diagnostic_unavailable',
        source_files=paths,source_sha256=bundle['source_sha256'],source_unchanged=True,model_modified=False,
        weighting=dict(source='paired CIF _refine_ls_weighting_details',formula=formula,parameters=weights,reasons=reasons),
        analysed_FCF_rows=len(rows),active_FCF_rows=len(active),excluded_status_x_rows=len(rows)-len(active),weighted_gt10_count=len(weighted) if weights is not None else None,
        measured_sigma_gt10_count=len(unweighted),low_angle_negative_weighted_count=len(low) if weights is not None else None,
        weighted_outliers=weighted if weights is not None else None,top_reflections=ranked[:20],
        small_outlier_set_for_review=0<len(weighted)<=20 if weights is not None else None,
        FCF_row_fraction_flagged=len(weighted)/len(active) if weights is not None and active else None,
        theoretical_completeness_loss=None,omit_applied=False,
        limitations=['Weighted values reconstructed from rounded LIST 4 values and the standard CIF formula; compare native SHELXL/PLATON output near thresholds.',
                    'FCF row fraction is not completeness loss. No raw HKL row count is substituted for unique reflection completeness.',
                    'An outlier is not proof of overexposure, beamstop error or a correct model; review low-angle, weighting, model and instrument evidence.',
                    'No reflections are removed. A separately authorised OMIT comparison must preserve original HKL, record omissions and recompute completeness/validation.'],
        seconds=round(time.perf_counter()-start,4))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',required=True);p.add_argument('--stem',default='case');p.add_argument('--output',required=True)
    a=p.parse_args()
    try:
        r=audit(a.directory,a.stem);newjson(a.output,r)
        print(json.dumps({'status':r['status'],'weighted_gt10':r['weighted_gt10_count'],'output':a.output,'seconds':r['seconds']}));return 0
    except (ValueError,OSError,RuntimeError) as e:
        print(json.dumps({'status':'failed','error':str(e)}));return 2

if __name__=='__main__':raise SystemExit(main())
