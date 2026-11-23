"""Deterministic bilingual DOCX tables; bilingual scientific notes are supplied by the reviewer."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,time
from crystal_runtime import sha,write_json,run_command

def normalized_scalars(scalars):
    """Case-insensitive CIF data names; retain data values verbatim.

    Use this lookup view only. The audit dataset retains source tag spelling.
    """
    return {tag.lower():value for tag,value in scalars.items()}

def extract(cif):
    import gemmi
    b=gemmi.cif.read_file(str(cif)).sole_block()
    def value(tag):
        v=b.find_value(tag)
        return None if not v or v in {'?','.'} else gemmi.cif.as_string(v)
    def rows(tags):return [list(r) for r in b.find(tags)]
    scalars={item.pair[0]:value(item.pair[0]) for item in b if item.pair and not item.pair[0].lower().startswith('_shelx')}
    atoms=rows(['_atom_site_label','_atom_site_type_symbol','_atom_site_fract_x','_atom_site_fract_y','_atom_site_fract_z','_atom_site_U_iso_or_equiv','_atom_site_occupancy','_atom_site_adp_type'])
    if not atoms:raise ValueError('Required atom/occupancy/ADP-type loop absent')
    elements={r[0]:r[1] for r in atoms}
    ani=rows(['_atom_site_aniso_label','_atom_site_aniso_U_11','_atom_site_aniso_U_22','_atom_site_aniso_U_33','_atom_site_aniso_U_23','_atom_site_aniso_U_13','_atom_site_aniso_U_12'])
    expected={r[0] for r in atoms if r[-1]=='Uani'}
    if {r[0] for r in ani}!=expected:raise ValueError('ANI site/tensor rows differ; do not invent tensors for ISO sites')
    bonds=rows(['_geom_bond_atom_site_label_1','_geom_bond_atom_site_label_2','_geom_bond_distance','_geom_bond_site_symmetry_2'])
    angles=rows(['_geom_angle_atom_site_label_1','_geom_angle_atom_site_label_2','_geom_angle_atom_site_label_3','_geom_angle','_geom_angle_site_symmetry_1','_geom_angle_site_symmetry_3'])
    hb=rows(['_geom_hbond_atom_site_label_D','_geom_hbond_atom_site_label_H','_geom_hbond_atom_site_label_A','_geom_hbond_distance_DH','_geom_hbond_distance_HA','_geom_hbond_distance_DA','_geom_hbond_angle_DHA','_geom_hbond_site_symmetry_A'])
    sym=rows(['_space_group_symop_id','_space_group_symop_operation_xyz']) or rows(['_symmetry_equiv_pos_site_id','_symmetry_equiv_pos_as_xyz'])
    if not sym:
        ops=list(b.find_values('_space_group_symop_operation_xyz')) or list(b.find_values('_symmetry_equiv_pos_as_xyz'))
        # SHELXL exports ordered operations without an explicit ID column.
        if value('_audit_creation_method') and value('_audit_creation_method').startswith('SHELXL'):
            sym=[[str(i+1),gemmi.cif.as_string(op)] for i,op in enumerate(ops)]
    if not sym:raise ValueError('Unambiguous symmetry operation IDs required for report geometry codes')
    return {'cif_sha256':sha(cif),'scalars':scalars,'atoms':atoms,'ani':ani,
        'bonds':[r for r in bonds if all(elements.get(x) not in {'H','D'} for x in r[:2])],
        'angles':[r for r in angles if all(elements.get(x) not in {'H','D'} for x in r[:3])],
        'hbonds':[[r[0]+'–'+r[1]+'···'+r[2],*r[3:]] for r in hb],'symmetry':sym}

FIELDS=[
 ('化学式','Chemical formula','_chemical_formula_sum'),('式量 / g mol⁻¹','Formula weight / g mol⁻¹','_chemical_formula_weight'),
 ('空间群','Space group','_space_group_name_H-M_alt'),('温度 / K','Temperature / K','_diffrn_ambient_temperature'),
 ('晶胞测定反射数','Cell measurement reflections','_cell_measurement_reflns_used'),
 ('晶胞测定 θ min / max / °','Cell measurement θ min / max / °',['_cell_measurement_theta_min','_cell_measurement_theta_max']),
 ('吸收校正及透射率 min / max','Absorption correction and transmission min / max',['_exptl_absorpt_correction_type','_exptl_absorpt_correction_T_min','_exptl_absorpt_correction_T_max']),
 ('颜色 / 外形','Colour / habit',['_exptl_crystal_colour','_exptl_crystal_description']),
 ('尺寸 / mm','Dimensions / mm',['_exptl_crystal_size_max','_exptl_crystal_size_mid','_exptl_crystal_size_min']),
 ('波长 / Å','Wavelength / Å','_diffrn_radiation_wavelength'),
 ('a / b / c / Å','a / b / c / Å',['_cell_length_a','_cell_length_b','_cell_length_c']),
 ('α / β / γ / °','α / β / γ / °',['_cell_angle_alpha','_cell_angle_beta','_cell_angle_gamma']),
 ('V / Å³；Z','V / Å³; Z',['_cell_volume','_cell_formula_units_Z']),
 ('计算密度 / g cm⁻³','Calculated density / g cm⁻³','_exptl_crystal_density_diffrn'),
 ('μ / mm⁻¹；F000','μ / mm⁻¹; F000',['_exptl_absorpt_coefficient_mu','_exptl_crystal_F_000']),
 ('测量 / 独立 / 观测反射','Measured / unique / observed',['_diffrn_reflns_number','_reflns_number_total','_reflns_number_gt']),
 ('R int；完整度','R int; completeness',['_diffrn_reflns_av_R_equivalents','_diffrn_measured_fraction_theta_max']),
 ('θ min / max / °','θ min / max / °',['_diffrn_reflns_theta_min','_diffrn_reflns_theta_max']),
 ('数据 / 限制 / 参数','Data / restraints / parameters',['_refine_ls_number_reflns','_refine_ls_number_restraints','_refine_ls_number_parameters']),
 ('R1 / wR2 观测数据','R1 / wR2 observed data',['_refine_ls_R_factor_gt','_refine_ls_wR_factor_gt']),
 ('R1 / wR2 全部数据','R1 / wR2 all data',['_refine_ls_R_factor_all','_refine_ls_wR_factor_ref']),
 ('GoF；最大 shift/s.u.','GoF; maximum shift/s.u.',['_refine_ls_goodness_of_fit_ref','_refine_ls_shift/su_max']),
 ('残余密度 max / min / e Å⁻³','Residual density max / min / e Å⁻³',['_refine_diff_density_max','_refine_diff_density_min']),
 ('消光参数','Extinction parameter','_refine_ls_extinction_coef')]

def build_reports(cif,official,notes,output,qa,figure=None):
    return build_from_dataset(cif,extract(cif),official,notes,output,qa,figure)


def build_from_dataset(cif,data,official,notes,output,qa,figure=None):
    from docx import Document
    from docx.shared import Inches,Pt,RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    output=Path(output);qa=Path(qa)
    if data['cif_sha256']!=sha(cif):raise ValueError('Frozen CIF changed after report table extraction')
    write_json(qa/'table_dataset.json',data)
    scalars=normalized_scalars(data['scalars'])
    for language in ['zh','en']:
        if not notes.get(language,{}).get('summary') or not notes[language].get('methods'):
            raise ValueError('Reviewer-provided summary and methods required in both languages')
    payload={k:data[k] for k in ['atoms','ani','bonds','angles','hbonds','symmetry']}
    numeric_hash=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    outputs={};table_rows={};typography={}
    for lang in ['zh','en']:
        zh=lang=='zh'; doc=Document();sec=doc.sections[0]
        sec.page_width=Inches(8.5);sec.page_height=Inches(11)
        sec.top_margin=sec.bottom_margin=Inches(.65);sec.left_margin=sec.right_margin=Inches(.65)
        for st in doc.styles:
            if st.type==1:
                st.font.name='Calibri';st.font.size=Pt(10.5);st.font.color.rgb=RGBColor(0,0,0)
                st.element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'宋体')
                for x in list(st.element.iter(qn('w:pBdr'))):x.getparent().remove(x)
        for name,size in [('Title',19),('Heading 1',14),('Heading 2',11.5)]:
            doc.styles[name].font.size=Pt(size);doc.styles[name].font.bold=True
        doc.styles['Normal'].paragraph_format.space_after=Pt(6);doc.styles['Normal'].paragraph_format.line_spacing=1.12
        doc.styles['Footer'].font.size=Pt(8)
        doc.styles['Footer'].font.color.rgb=RGBColor(112,112,112)
        foot=sec.footer.paragraphs[0];foot.alignment=WD_ALIGN_PARAGRAPH.RIGHT
        foot.paragraph_format.space_after=Pt(0)
        attribution=('候选模型由 Cairystal 协助生成' if zh else 'Provisional model generated with Cairystal') if notes.get('provisional') else ('结构解析与精修由 Cairystal 协助完成' if zh else 'Structure solution and refinement assisted by Cairystal')
        foot.add_run(attribution+'  ·  ')
        foot.add_run('第 ' if zh else 'Page ');f=OxmlElement('w:fldSimple');f.set(qn('w:instr'),'PAGE');foot._p.append(f)
        if zh:foot.add_run(' 页')
        def p(text):return doc.add_paragraph(text)
        def page(title):
            heading=doc.add_heading(title,1)
            heading.paragraph_format.page_break_before=True
        def table(headers,values,widths,size=9.5):
            t=doc.add_table(rows=1,cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
            for c,w in zip(t.columns,widths):c.width=Inches(w)
            for cell,text in zip(t.rows[0].cells,headers):cell.text=str(text)
            t.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
            for row in values:
                for cell,text in zip(t.add_row().cells,row):cell.text=str(text)
            borders=OxmlElement('w:tblBorders')
            for edge in ['top','left','bottom','right','insideH','insideV']:
                x=OxmlElement('w:'+edge);x.set(qn('w:val'),'single');x.set(qn('w:sz'),'4');x.set(qn('w:color'),'D9D9D9');borders.append(x)
            t._tbl.tblPr.append(borders)
            for i,row in enumerate(t.rows):
                row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
                for cell,w in zip(row.cells,widths):
                    cell.width=Inches(w)
                    if i==0:
                        x=OxmlElement('w:shd');x.set(qn('w:fill'),'F2F2F2');cell._tc.get_or_add_tcPr().append(x)
                    for para in cell.paragraphs:
                        para.paragraph_format.space_after=Pt(1);para.paragraph_format.space_before=Pt(1);para.paragraph_format.line_spacing=1
                        if i==0:para.paragraph_format.keep_with_next=True
                        for run in para.runs:run.font.size=Pt(size);run.font.bold=i==0
            # A spacer paragraph can spill onto a new page by itself before a
            # heading-level page break. Use paragraph styles for section spacing.
            return t
        title=notes.get(lang,{}).get('title') or ('晶体学报表' if zh else 'Crystallographic report')
        doc.add_paragraph(title,'Title');p(notes[lang]['summary'])
        counts=official['counts'];p(('IUCr 官网警告 ' if zh else 'Official IUCr alerts ')+ ' / '.join(f'{counts[k]} {k}' for k in 'ABCG'))
        doc.add_heading('晶体数据与精修结果' if zh else 'Crystal data and refinement',1)
        vals=[]
        for cn,en,tags in FIELDS:
            tags=tags if isinstance(tags,list) else [tags]
            if notes.get('provisional') and tags==['_chemical_formula_sum']:cn,en='当前模型计数式','Current model atom-count formula'
            value=' / '.join(scalars.get(t.lower()) or ('未提供' if zh else 'Not supplied') for t in tags)
            vals.append([cn if zh else en,value])
        table(['项目','本次结果'] if zh else ['Item','Result'],vals,[2.55,4.65],10)
        p('完整度以 0–1 的分数表示。表中观测数据阈值以 CIF 定义为准。' if zh else 'Completeness is a fraction from 0 to 1. The observed-data threshold is defined by the CIF.')
        page('模型解释与精修方法' if zh else 'Model interpretation and refinement')
        if figure:
            doc.add_picture(str(figure),width=Inches(6.9))
            p('本次匹配 CIF 的官方 PLATON 图。显示的对称扩展原子不是额外独立位点。' if zh else 'Official PLATON plot for the matched CIF. Symmetry-generated display atoms are not additional independent sites.')
        p(notes[lang]['methods'])
        # A short methods paragraph without a figure need not occupy its own page.
        if figure:page('原子坐标与占有率' if zh else 'Atomic coordinates and occupancies')
        else:doc.add_heading('原子坐标与占有率' if zh else 'Atomic coordinates and occupancies',1)
        p('分数坐标；Ueq 或 Uiso 单位为 Å²；括号为标准不确定度。占有率和 Uani/Uiso 按最终 CIF 原样报告。' if zh else 'Fractional coordinates; Ueq or Uiso in Å². Parentheses denote standard uncertainties. Occupancies and Uani/Uiso types are reported directly from the final CIF.')
        table(['原子','元素','x','y','z','Ueq/Uiso','占有率','类型'] if zh else ['Atom','El.','x','y','z','Ueq/Uiso','Occ.','Type'],data['atoms'],[.8,.5,1.2,1.2,1.2,1.1,.6,.6],9)
        # Coordinates may end with only a few rows on a continuation page.
        # Flow the ADP section into the remaining body area instead of wasting it.
        doc.add_heading('各向异性位移参数' if zh else 'Anisotropic displacement parameters',1)
        p('Uij 单位为 Å²，采用 CIF 晶体学坐标定义。各向同性位点不出现在此表中。' if zh else 'Uij values are in Å² using the CIF crystallographic basis. Isotropic sites are excluded from this table.')
        table(['原子' if zh else 'Atom','U11','U22','U33','U23','U13','U12'],data['ani'],[.75,1.075,1.075,1.075,1.075,1.075,1.075],9)
        doc.add_heading('非氢原子键长' if zh else 'Non-hydrogen bond lengths',2)
        table(['原子1','原子2','距离 / Å','原子2对称码'] if zh else ['Atom 1','Atom 2','Distance / Å','Symmetry 2'],data['bonds'],[1.2,1.2,2.4,2.4])
        page('非氢原子键角' if zh else 'Non-hydrogen bond angles')
        table(['原子1','原子2','原子3','角度 / °','对称码1','对称码3'] if zh else ['Atom 1','Atom 2','Atom 3','Angle / °','Sym. 1','Sym. 3'],data['angles'],[.9,.9,.9,1.5,1.5,1.5])
        p('表格仅按原子元素筛除含 H/D 的键长键角，未重新判定 CIF 中每个接触的化学性质。' if zh else 'H/D-containing covalent geometry is excluded by element. The chemical validity of every CIF-listed contact is not reassessed by this formatter.')
        doc.add_heading('供氢接触与对称码' if zh else 'Donor contacts and symmetry codes',1)
        if data['hbonds']:
            table(['D–H···A','D–H / Å','H···A / Å','D···A / Å','角度 / °','对称码A'] if zh else ['D–H···A','D–H / Å','H···A / Å','D···A / Å','Angle / °','Sym. A'],data['hbonds'],[1.8,.9,.9,1.3,1,1.3],9)
        else:p('CIF 未提供氢键表；不能据此认定不存在氢键。' if zh else 'No hydrogen-bond table is supplied in the CIF; this does not establish absence of hydrogen bonding.')
        p('长距离或弯曲接触不等于已确认的强氢键。' if zh else 'Long or bent contacts do not establish strong hydrogen bonds.')
        table(['编号','对称操作'] if zh else ['ID','Symmetry operation'],data['symmetry'],[1,6.2])
        p('对称码 n_abc 表示采用编号 n 的操作后，分别平移 (a−5,b−5,c−5) 个晶胞；点号为原位。' if zh else 'Code n_abc applies operation n followed by translation (a−5,b−5,c−5) in unit cells. A dot denotes the original site.')
        doc.add_heading('验证结果与限制' if zh else 'Validation findings and limitations',1)
        p('以下逐条列出官网 A/B 警告；已支持的条目给出中文概述，重复代码不合并。完整数值与 A/B/C/G 原文见随附官方 PDF。' if zh else 'Every official A/B alert is retained below. Repeated codes refer to distinct sites or peaks and are not merged. See the official PDF for the full C/G findings.')
        alerts=[a for a in official['alerts'] if a['level'] in 'AB']
        if not alerts:p('官网未报告 A/B 警告；这本身不能证明结构正确。' if zh else 'No A/B alerts were reported; this alone does not establish structural correctness.')
        for a in alerts:
            doc.add_heading(a['code'],2)
            explanation=notes[lang].get('alert_explanations',{}).get(a['code'])
            localized=notes[lang].get('alert_texts',{}).get(a['code']+'|'+a['text']) or notes[lang].get('alert_texts',{}).get(a['code'])
            if zh and not localized:
                key=a['code'].split('_ALERT')[0].removeprefix('PLAT')
                localized={'EXPT005':'未提供晶体外形。','DIFF003':'未提供衍射仪型号。',
                    '183':'未提供晶胞测定使用的反射数。','184':'未提供晶胞测定的最小 θ 角。',
                    '185':'未提供晶胞测定的最大 θ 角。','197':'未提供晶胞测量温度。',
                    '198':'未提供衍射数据采集温度。','699':'未提供晶体外形描述。',
                    '196':'RES 中没有 TEMP，且 CIF 温度信息与软件默认处理不符；应核对温度来源及同步，不能把默认值当作实测值。',
                    '910':'低角区域存在缺失反射；需核对原始 HKL 与结构因子文件。完整阈值和数值见官网 PDF。'}.get(key)
            p(localized if zh and localized else a['text'])
            if explanation:p(explanation)
        if notes[lang].get('limitations'):p(notes[lang]['limitations'])
        p(('模型来源与分析模式：' if zh else 'Model provenance and analysis mode: ')+notes[lang].get('provenance','未提供' if zh else 'Not supplied'))
        p('数值收敛、低 R 值或无 A/B 警告均不能替代化学与晶体学复核。' if zh else 'Numerical convergence, low R values or absence of A/B alerts cannot replace chemical and crystallographic review.')
        from report_typography import apply as apply_typography,contact_text
        p(contact_text(zh))
        typography[lang]=apply_typography(doc)
        name='晶体学报表_中文.docx' if zh else 'Crystallographic_Report_EN.docx';path=output/name;doc.save(path)
        reopened=Document(path);table_rows[lang]=[[[c.text for c in row.cells] for row in t.rows[1:]] for t in reopened.tables]
        outputs[lang]={'path':str(path),'sha256':sha(path),'data_sha256':numeric_hash}
    # First table differs only in the localized field names, not scientific values.
    a=table_rows['zh'];b=table_rows['en']
    if [r[1:] for r in a[0]]!=[r[1:] for r in b[0]]:
        # Missing values have intentional localized strings.
        norm=lambda x:str(x).replace('未提供','Not supplied')
        if norm([r[1:] for r in a[0]])!=norm([r[1:] for r in b[0]]):raise ValueError('Bilingual scalar tables differ')
    if a[1:]!=b[1:]:raise ValueError('Bilingual numerical tables differ')
    record={'outputs':outputs,'same_numeric_tables':True,'cif_sha256':sha(cif),'row_counts':{k:len(data[k]) for k in payload},'visual_review':'pending','typography':typography}
    write_json(qa/'report_build.json',record);return record

def render_reports(reports,qa,renderer,pdftoppm,soffice=None,powershell=None,render_cache=None):
    """Select the supplied renderer once; render both languages; retain only internal previews."""
    from pypdf import PdfReader
    started=time.perf_counter();timings={}
    from report_render_cache import contract,restore
    qa=Path(qa)
    stamp,context_reason=contract(reports,renderer,pdftoppm,soffice,powershell)
    reused,cache_reason=restore(render_cache,qa,reports,stamp)
    if reused is not None:
        reused['elapsed_s']=round(time.perf_counter()-started,6)
        write_json(qa/'render_manifest.json',reused)
        return reused
    timings['cache_preflight']=round(time.perf_counter()-started,6)
    render_dir=qa/'render';render_dir.mkdir();jobs=[]
    for lang,rec in reports['outputs'].items():
        folder=render_dir/lang;folder.mkdir()
        jobs.append({'language':lang,'docx':str(Path(rec['path']).absolute()),'pdf':str((folder/'report.pdf').absolute())})
    if renderer=='word':
        if os.name!='nt':raise ValueError('Word COM renderer requires Windows')
        if not powershell or not Path(powershell).is_file():raise ValueError('Supply the approved host PowerShell executable with --powershell; do not change execution policies')
        config=qa/'render_config.json';write_json(config,jobs)
        script=qa/'render_word.ps1'
        script.write_text('''param([string]$ConfigPath)
$ErrorActionPreference='Stop'
$jobs=Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
$word=New-Object -ComObject Word.Application
$word.Visible=$false
$word.DisplayAlerts=0
try { foreach($j in $jobs) { $doc=$null; try { $doc=$word.Documents.Open([string]$j.docx,$false,$true); $doc.ExportAsFixedFormat([string]$j.pdf,17) } finally { if($null -ne $doc){$doc.Close(0)} } } }
finally { $word.Quit(); [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) }
''',encoding='utf-8-sig')
        cmd=[powershell,'-NoProfile','-File',str(script),'-ConfigPath',str(config)]
        result=run_command(cmd,qa,qa/'renderer.log',240)
        timings['word_pdf_export']=result['elapsed_s']
        if result['returncode']!=0 or result['process_state']!='finished':raise ValueError('Word render failed; see renderer.log')
    elif renderer=='libreoffice':
        if not soffice:raise ValueError('Supply --soffice for LibreOffice renderer')
        for j in jobs:
            folder=Path(j['pdf']).parent;profile=folder/'lo_profile';profile.mkdir()
            res=run_command([soffice,'-env:UserInstallation='+profile.as_uri(),'--headless','--convert-to','pdf','--outdir',folder,j['docx']],qa,folder/'renderer.log',180)
            timings['libreoffice_pdf_export_'+j['language']]=res['elapsed_s']
            generated=folder/(Path(j['docx']).stem+'.pdf')
            if res['returncode'] or not generated.exists():raise ValueError('LibreOffice render failed')
            generated.rename(j['pdf'])
    else:raise ValueError('Choose an available renderer: word or libreoffice')
    for j in jobs:
        pdf=Path(j['pdf']);prefix=pdf.parent/'page';res=run_command([pdftoppm,'-r','110','-png',pdf,prefix],qa,pdf.parent/'raster.log',180)
        timings['page_raster_'+j['language']]=res['elapsed_s']
        pages=sorted(pdf.parent.glob('page-*.png'))
        if res['returncode'] or len(pages)!=len(PdfReader(pdf).pages):raise ValueError('Incomplete rendered page set')
        j['pages']=[{'path':str(p),'sha256':sha(p)} for p in pages];j['pdf_sha256']=sha(pdf)
    final_stamp,final_reason=contract(reports,renderer,pdftoppm,soffice,powershell)
    if final_stamp!=stamp:
        stamp=None;context_reason='Document/render context changed during rendering; cache disabled'
    record={'renderer':renderer,'jobs':jobs,'visual_review':'pending','timings_s':timings,
        'cache_hit':False,'cache_miss_reason':context_reason or cache_reason,
        'render_contract':stamp,'elapsed_s':round(time.perf_counter()-started,6)}
    write_json(qa/'render_manifest.json',record);return record
