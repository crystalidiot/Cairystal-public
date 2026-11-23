"""Validate a modern unscaled ABIN/FAB contribution without inferring solvent identity."""
import math,re
from pathlib import Path
import gemmi
from crystal_runtime import regular,sha,records

def parse_fab(text):
 rows=[];terminated=False;tail=[]
 for line in text.splitlines():
  if terminated:tail.append(line);continue
  if not line.strip() or line.lstrip().startswith('#'):continue
  f=line.split()
  if len(f)!=5:raise ValueError('FAB reflection requires h k l A B')
  hkl=tuple(int(x) for x in f[:3]);ab=[float(x) for x in f[3:]]
  if not all(math.isfinite(x) for x in ab):raise ValueError('Nonfinite FAB contribution')
  if hkl==(0,0,0):terminated=True;continue
  rows.append([*hkl,*ab])
 if not terminated or not rows:raise ValueError('Incomplete/empty FAB reflection section')
 if len({tuple(r[:3]) for r in rows})!=len(rows):raise ValueError('Duplicate FAB reflections')
 b=gemmi.cif.read_string('data_mask\n'+'\n'.join(tail)+'\n').sole_block()
 tags=['_platon_squeeze_void_'+x for x in ['nr','average_x','average_y','average_z','volume','count_electrons','content']]
 table=b.find(tags)
 if not table:raise ValueError('PLATON SQUEEZE void metadata absent from FAB')
 voids=[]
 for r in table:
  row=list(r);nums=[gemmi.cif.as_number(v) for v in row[1:6]]
  if any(not math.isfinite(v) for v in nums) or nums[3]<0:raise ValueError('Invalid SQUEEZE void values')
  voids.append({'number':int(row[0]),'centre':nums[:3],'volume_A3':nums[3],'electrons':nums[4],'content':gemmi.cif.as_string(row[6]).strip() or None})
 details=b.find_value('_platon_squeeze_details')
 if not details:raise ValueError('SQUEEZE calculation details absent from FAB')
 return {'rows':rows,'voids':voids,'metadata':b.as_string(),'volume_A3':sum(v['volume_A3'] for v in voids),'electrons_per_cell':sum(v['electrons'] for v in voids),'quality_flags':['negative_void_electron_count'] if any(v['electrons']<0 for v in voids) else [],'solvent_identity':'not_determined_by_electron_count'}

def verify(directory,stem,block,text):
 lines=records(text);abin=[r for r in lines if r[0].upper()=='ABIN']
 if not abin:return None
 if len(abin)!=1 or abin[0][1:] not in [[],['1','0']]:raise ValueError('Scaled/parameterized ABIN requires a specialist audit')
 fab=regular(Path(directory)/(stem+'.fab'));raw=fab.read_text('latin1');parsed=parse_fab(raw)
 embedded=block.find_value('_shelx_fab_file')
 if not embedded:raise ValueError('CIF does not embed its matching FAB contribution')
 # SHELXL protects embedded CIF text-field delimiters with a leading ')'.
 # Decode only the embedded FAB, then compare the complete parsed metadata.
 embedded_text=gemmi.cif.as_string(embedded)
 embedded_text='\n'.join(';'+line[1:] if line.startswith(')') else line for line in embedded_text.splitlines())+'\n'
 other=parse_fab(embedded_text)
 if parsed['rows']!=other['rows'] or parsed['metadata']!=other['metadata']:raise ValueError('CIF embedded FAB differs from actual FAB')
 return {k:v for k,v in parsed.items() if k not in ['rows','metadata']}|{'path':str(fab),'sha256':sha(fab),'contribution_rows':len(parsed['rows']),'active_ABIN':abin[0],'scientific_acceptance':False}

def companion_fab(res):
 res=regular(res);text=res.read_text('latin1')
 if not any(r[0].upper()=='ABIN' for r in records(text)):return None
 cif=regular(res.with_suffix('.cif'));block=gemmi.cif.read_file(str(cif)).sole_block()
 return Path(verify(res.parent,res.stem,block,text)['path'])

def bilingual_notes(mask):
 volume=mask['volume_A3'];e=mask['electrons_per_cell']
 return {'zh':{'methods':f'使用 PLATON SQUEEZE 估计溶剂可及区域的散射贡献，并通过 SHELXL ABIN/FAB 计入计算结构因子。孔隙总体积为 {volume:g} Å³，每晶胞积分电子数为 {e:g}。原始衍射强度保留。', 'limitations':'积分电子数不能唯一确定溶剂身份或准确计量。显式主体模型与被处理的溶剂贡献需分开报告；化学式、式量、密度和 F(000) 的组成范围须核实。SQUEEZE 不能证明主体或溶剂结构正确。'},'en':{'methods':f'PLATON SQUEEZE estimated scattering from solvent-accessible regions, included in calculated structure factors through SHELXL ABIN/FAB. The total void volume is {volume:g} A^3 and the integrated count is {e:g} electrons per unit cell. Original measured intensities were retained.','limitations':'Integrated electrons do not uniquely establish solvent identity or stoichiometry. The explicit host and masked contribution must be reported separately, with the composition basis of formula, formula weight, density and F(000) reviewed. SQUEEZE does not establish structural correctness.'}}
