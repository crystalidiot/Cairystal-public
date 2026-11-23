"""Bounded read-only evidence tools automatically attached to relevant A/B routes."""
from pathlib import Path
import importlib
from structure_diagnostics import newjson


def collect(base, alerts, output):
    codes={str(a['code']) for a in alerts};jobs=[];results=[]
    if codes & {'306','417','420','430'}:jobs.append(('donor-audit','donor_audit'))
    if codes & {'918','919','934','939'}:jobs.append(('reflection-audit','reflection_audit'))
    if codes & {'019','020','023','026','027','028','029','905','906','910','911','912','913','934','939'}:jobs.append(('resolution-shells','resolution_shells'))
    if codes & {'080','081','SHFSU01','214','234'}:jobs.append(('parameter-correlations','parameter_correlations'))
    if codes & {'211','212','213','214','215','216'}:jobs.append(('adp-directions','adp_directions'))
    if codes & {'088','089','090','904','REFNR01'}:jobs.append(('parameter-budget','parameter_budget'))
    if codes & ({str(x) for x in range(711,759)}|{'069','070','071','720','SYMOP01'}):jobs.append(('geometry-audit','geometry_audit'))
    if codes & {'006','031','080','SHFSU01','731','732','935','936'}:jobs.append(('refinement-controls','refinement_controls'))
    for tool,module in jobs:
        target=Path(output)/(tool+'.json')
        try:
            fn=importlib.import_module(module).audit
            evidence=fn(base);newjson(target,evidence)
            results.append({'tool':tool,'status':evidence['status'],'path':str(target),
                            'seconds':evidence['seconds'],'model_modified':False})
        except Exception as exc:
            # A diagnostic failure must remain visible without suppressing other tools.
            results.append({'tool':tool,'status':'failed','error':str(exc),'exception_type':type(exc).__name__,'path':None,'model_modified':False})
    return results
