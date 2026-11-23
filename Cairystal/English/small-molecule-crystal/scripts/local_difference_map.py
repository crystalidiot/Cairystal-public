"""Unweighted (Fo-Fc) map from native SHELXL LIST 6; explicit diagnostic only.

Validated route currently restricted to centrosymmetric exported phase sets.
Requires Gemmi and NumPy. Does not calculate observed intensities from a model.
"""
from pathlib import Path
import argparse,hashlib,json,math,re,time
import gemmi
import numpy as np
from structure_diagnostics import res_records,digest,newjson,structure

def calculate(fcf,output,baseline_cif,baseline_res,labels,radius=1.6,step=.2):
 if not all(math.isfinite(v) and v>0 for v in [radius,step]) or (math.ceil(2*radius/step)+1)**3>2000000:raise ValueError('Invalid or excessive local map sampling')
 start=time.perf_counter();fcf=Path(fcf);out=Path(output)
 if out.exists():raise FileExistsError(str(out))
 out.mkdir(parents=True)
 b=gemmi.cif.read_file(str(fcf)).sole_block()
 if b.find_value('_shelx_refln_list_code')!='6':raise ValueError('Native LIST 6 FCF required')
 cell=gemmi.UnitCell(*[gemmi.cif.as_number(b.find_value('_cell_'+v)) for v in ['length_a','length_b','length_c','angle_alpha','angle_beta','angle_gamma']])
 ops=gemmi.GroupOps([gemmi.Op(gemmi.cif.as_string(v)) for v in b.find_values('_space_group_symop_operation_xyz')]);sg=gemmi.find_spacegroup_by_ops(ops)
 if sg is None or not sg.is_centrosymmetric():raise ValueError('This tested map route currently requires a centrosymmetric setting')
 baseblock,basecell,_,atoms,_=structure(baseline_cif,baseline_res)
 from crystal_runtime import symmetry_operations
 if symmetry_operations(b)!=symmetry_operations(baseblock):raise ValueError('Map/model symmetry setting mismatch')
 if max(abs(x-y) for x,y in zip(cell.parameters,basecell.parameters))>.01:raise ValueError('Map/model cell mismatch')
 tags=['_refln_index_h','_refln_index_k','_refln_index_l','_refln_F_squared_meas','_refln_F_squared_sigma','_refln_F_calc','_refln_phase_calc']
 rows=np.array([[float(v) for v in row] for row in b.find(tags)],dtype=float)
 if not len(rows) or not np.isfinite(rows).all():raise ValueError('Missing/nonfinite LIST6 data')
 if not np.equal(rows[:,:3],np.round(rows[:,:3])).all():raise ValueError('Noninteger reflection indices are not permitted')
 hkl=rows[:,:3].astype(np.int32)
 if len({tuple(x) for x in hkl})!=len(hkl):raise ValueError('Duplicate hkl records need explicit merging review')
 coefficients=((np.sqrt(np.maximum(rows[:,3],0))-rows[:,5])*np.exp(1j*np.deg2rad(rows[:,6]))).astype(np.complex64)
 data=gemmi.ComplexAsuData(cell,sg,hkl,coefficients)
 dimensions=data.get_size_for_hkl(sample_rate=4)
 if math.prod(dimensions)>20000000:raise ValueError('Map size exceeds bounded local diagnostic route')
 grid=data.transform_f_phi_to_map(sample_rate=4)
 ccp4=gemmi.Ccp4Map();ccp4.grid=grid;ccp4.update_ccp4_header();ccp4.write_ccp4_map(str(out/'difference.ccp4'))
 atommap={a['label'].upper():a for a in atoms};regions=[]
 offsets=np.arange(-radius,radius+step*.1,step)
 for label in labels:
  atom=atommap[label.upper()];centre=cell.orthogonalize(gemmi.Fractional(*atom['xyz']));values=[];points=[]
  for x in offsets:
   for y in offsets:
    for z in offsets:
     if x*x+y*y+z*z>radius*radius:continue
     frac=cell.fractionalize(gemmi.Position(centre.x+x,centre.y+y,centre.z+z))
     value=grid.interpolate_value(frac);values.append(value);points.append([frac.x,frac.y,frac.z])
  val=np.array(values);order=np.argsort(val);maxi=int(order[-1]);mini=int(order[0])
  regions.append({'label':label,'centre_fractional':atom['xyz'],'radius_A':radius,'step_A':step,'points':len(val),
    'density_at_atom':grid.interpolate_value(gemmi.Fractional(*atom['xyz'])),
    'local_max':float(val[maxi]),'max_fractional':points[maxi],
    'local_min':float(val[mini]),'min_fractional':points[mini],
    'rms_about_zero':float(np.sqrt(np.mean(val*val))),
    'positive_integral_on_sample_grid':float(np.maximum(val,0).sum()*step**3),
    'integral_scope':'Overlapping atom-centred spheres and Fourier truncation: not a solvent electron count or formula.'})
 native_peaks=res_records(fcf.with_suffix('.res'))['peaks'] if fcf.with_suffix('.res').exists() else []
 comparisons=[]
 for peak in native_peaks[:10]:
  calc=grid.interpolate_value(gemmi.Fractional(*peak['xyz']))
  comparisons.append({'label':peak['label'],'SHELXL_peak':peak['height'],'Gemmi_at_reported_coordinate':calc,'difference':calc-peak['height']})
 result={'schema':1,'source_fcf':str(fcf),'source_sha256':digest(fcf),'baseline_cif_sha256':digest(baseline_cif),
   'method':'(sqrt(max(Fo2,0))-Fc)*exp(i*phi_calc); crystallographic FFT normalized by cell volume',
   'space_group':sg.xhm(),'reflections':len(rows),'negative_Fo2_clipped_for_map':int((rows[:,3]<0).sum()),
   'grid_dimensions':list(grid.shape),'grid_max':float(grid.array.max()),'grid_min':float(grid.array.min()),'grid_rms':float(grid.array.std()),
   'regions':regions,'SHELXL_peak_comparison':comparisons,'seconds':time.perf_counter()-start,
   'limitations':['Phase-biased omit map; not proof of atom identity or occupancy.',
    'Unweighted map coefficients and interpolation may differ from SHELXL peak optimization.',
    'No OMIT reflections; all LIST6 exported observations used. Native export is a derived representation, not original raw data.',
    'Positive integral is diagnostic only, not absolute electron counting.']}
 newjson(out/'map_summary.json',result);return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--fcf',required=True);p.add_argument('--output',required=True);p.add_argument('--baseline-cif',required=True);p.add_argument('--baseline-res',required=True);p.add_argument('--labels',nargs='+',required=True)
 a=p.parse_args();v=calculate(a.fcf,a.output,a.baseline_cif,a.baseline_res,a.labels);print(json.dumps({'output':a.output,'seconds':v['seconds'],'regions':v['regions']},ensure_ascii=False))
