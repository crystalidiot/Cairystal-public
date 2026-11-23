"""Read-only historical report statement audit, not authentication or acceptance."""
import argparse
import hashlib
import json
import re
from pathlib import Path

def assess_text(text):
    plain=re.sub(r'<[^>]*>', ' ',text)
    supplied=bool(re.search(r'Structure\s+factors\s+have\s+been\s+supplied',plain,re.I))
    missing=bool(re.search(r'(?:You\s+have\s+not\s+supplied\s+any\s+structure\s+factors|No\s+structure\s+factors\s+(?:were|have\s+been)\s+supplied)',plain,re.I))
    basic=bool(re.search(r'A\s+basic\s+structural\s+check\s+has\s+been\s+run',plain,re.I))
    publication=bool(re.search(r'full\s+publication\s+checks?\s+(?:have|has)\s+been\s+run',plain,re.I))
    status='mixed_statements_requires_block_review' if supplied and missing else 'no_structure_factors' if missing else 'supplied_statement_requires_sections_review' if supplied else 'scope_unknown'
    warnings=[]
    if missing:warnings.append('Zero A/B cannot establish structure-factor validation when factors were not supplied')
    if basic:warnings.append('Basic checks are not confirmation of full publication checks')
    if supplied:warnings.append('Supplied statement does not authenticate report, verify exact current CIF pairing or establish scientific acceptance')
    if not supplied and not missing:warnings.append('Validation depth cannot be established from this text')
    return {'status':status,'structure_factors_supplied_statement':supplied,'structure_factors_missing_statement':missing,
            'basic_check_statement':basic,'full_publication_check_statement':publication,
            'official_authenticity_verified':False,'exact_current_cif_pairing_verified':False,
            'scientific_acceptance':False,'warnings':warnings}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('text_file',type=Path)
    args=parser.parse_args();raw=args.text_file.read_bytes()
    text=raw.decode('utf-8-sig',errors='replace')
    print(json.dumps({'path':str(args.text_file.resolve()),'sha256':hashlib.sha256(raw).hexdigest(),**assess_text(text)},ensure_ascii=False,indent=2))
