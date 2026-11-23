'use strict';
let policy;
const $=id=>document.getElementById(id);
const details={
'214':['自动试局部 ISOR，并与不改模型的继续精修比较','要求唯一的各向异性原子；已有部分占有、疑似未解无序、明显差值峰或指认冲突时，先交给诊断。'],
'234':['分别试 RIGU 与 SIMU','要求明确的同 PART 原子对和合理的近邻关系。不会不加区分地给整个分子加限制。'],
'242':['比较已有 SFAC 中的 C/N/O 候选','不改变原始数据；涉及骑乘氢、占有率或复杂无序时，需补齐化学方案。'],
'420':['对已确认的简单 C–O–H 生成有限转动候选，使用 AFIX 3','要求现有 O–H、唯一碳锚点和全占有普通位置。水和 N–H 不套用这个模板。'],
'080':['先定位最后一轮不收敛参数，再判断是否试 AFIX 3','只有明确属于可处理骑乘氢的情况会自动准备方案；不会直接固定所有原子的坐标。'],
'183':['自动定位实验参数工具，等待同实验的参数来源','缺参数不会改结构来解决，也不会把全 HKL 数量当作测晶胞使用的反射数。'],
'934':['定位异常反射诊断工具，保留原始 HKL','警告编号本身不能证明过曝。先核对偏差、完整度与可能的模型/数据原因，现有诊断工具继续可用。']};
function route(){const d=details[$('alert').value];$('route').replaceChildren();const b=document.createElement('b');b.textContent=d[0];const p=document.createElement('p');p.textContent=d[1];$('route').append(b,p);}
fetch('/ab-policy.json').then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json()}).then(data=>{
 policy=data;for(const s of data.mainline){const d=document.createElement('div');d.className='step';const n=document.createElement('span');n.className='num';n.textContent=s.id;const title=document.createElement('b');title.textContent=s.title;const p=document.createElement('p');p.textContent=s.action;d.append(n,title,p);$('steps').append(d);}
 $('budget').value=data.max_hypotheses;$('budgetValue').textContent=data.max_hypotheses;$('auto').checked=data.automatic_candidates;
 $('version').textContent='ab_mainline_20261106_01 · 规则来自 assets/ab_policy.json · 参数保存到包外；完整计算记录由任务保存。';route();
}).catch(e=>{$('version').textContent='规则读取失败：'+e.message;$('download').disabled=true;});
$('alert').addEventListener('change',route);
$('budget').addEventListener('input',()=>{$('budgetValue').textContent=$('budget').value;});
$('download').addEventListener('click',()=>{if(!policy)return;const data={automatic_candidates:$('auto').checked,max_hypotheses:Number($('budget').value)};const u=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)+'\n'],{type:'application/json'}));const a=document.createElement('a');a.href=u;a.download='ab-policy.user.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);$('notice').textContent='已生成参数文件。交给 agent 挂到新任务的 ab_policy 配置；尚未修改任何模型或任务。';});
