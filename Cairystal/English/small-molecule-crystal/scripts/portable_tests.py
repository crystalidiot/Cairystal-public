"""Run bounded offline synthetic regressions; never upload or solve a customer case."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

MODULES = [
    'test_usage_optimization',
    'test_chemistry_first',
    'test_flow_handoffs',
    'test_working_omit',
    'test_case_resume',
    'test_measured_seed',
    'test_ab_automation',
    'test_repair_plan','test_common_disorder','test_candidate_trials','test_handoff_diagnostics',
    'test_atom_labels','test_report_support','test_experimental_sidecar',
    'test_metadata_state_and_comparison','test_temperature_consistency',
    'test_report_rule_review','test_customer_delivery','test_delivery_completion',
    'test_delivery_automation','test_review_delivery','test_crystal_pipeline',
    'test_crystal_autorun','test_review_regressions','test_platon_pdf_completion',
    'test_routine_session','test_routine_consistency','test_novice_reliability',
    'test_language_intake','test_cif_tag_case','test_intake_image_upload',
    'test_experiment_metadata','test_project_metadata_preflight',
    'test_twin_delivery','test_processing_gates','test_toolbox',
    'test_workflow_reliability','test_initial_model_review','test_problem_routes','test_console_release_reuse',
    'test_pipeline_boundaries',
]

def main():
    # Child CLI tests read JSON as UTF-8; -X utf8 on this process is not inherited.
    os.environ['PYTHONUTF8']='1'
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True)
    p.add_argument('--module-dir',action='append',default=[])
    a=p.parse_args()
    from pipeline_intake import unlinked
    from crystal_runtime import new_directory,write_json
    out=new_directory(unlinked(a.output))
    scratch=out/'scratch';scratch.mkdir()
    tempfile.tempdir=str(scratch)
    for path in a.module_dir:
        sys.path.append(str(unlinked(path)))
    root=Path(__file__).resolve().parent.parent
    sys.path.insert(0,str(root/'scripts'))
    sys.path.insert(0,str(root/'tests'))
    sys.dont_write_bytecode=True
    start=time.perf_counter()
    with (out/'tests.log').open('w',encoding='utf-8') as log:
        suite=unittest.defaultTestLoader.loadTestsFromNames(MODULES)
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    info={'schema':1,'modules':MODULES,'tests':result.testsRun,'failures':len(result.failures),
          'errors':len(result.errors),'skipped':len(result.skipped),'success':result.wasSuccessful(),
          'seconds':round(time.perf_counter()-start,3),'log':str(out/'tests.log'),
          'native_program_execution':False,'official_upload':False,'new_crystal_solved':False,
          'scope':'Offline synthetic logic and delivery-gate regressions; not scientific correctness or host compatibility certification.'}
    write_json(out/'results.json',info)
    print(json.dumps(info,ensure_ascii=False))
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':raise SystemExit(main())
