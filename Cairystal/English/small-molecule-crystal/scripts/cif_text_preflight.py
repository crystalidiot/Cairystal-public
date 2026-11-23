"""CIF1 text boundary: reversible narrative encoding, protected data and local rejection."""
from pathlib import Path
import json,re
import gemmi
from crystal_runtime import sha, write_json
from prepare_validation_metadata import snapshot

NARRATIVE_TAGS = {'_publ_section_exptl_refinement', '_exptl_absorpt_special_details'}
CAIRYSTAL_COMMENT = b'# Structure solution and refinement assisted by Cairystal.'


def add_assistance_comment(path, audit_path):
    """Credit on a derived final CIF before validation; preserve all original bytes.

    Insert outside data/text fields, retain a leading CIF1 version declaration,
    and never serialize the document to add a comment. The caller keeps original
    experimental inputs immutable. Official submission/hashes follow this step.
    """
    path, audit_path = Path(path), Path(audit_path)
    if audit_path.exists(): raise ValueError('CIF attribution audit already exists')
    check_ascii(path)
    raw = path.read_bytes()
    if raw.startswith(b'#\\#CIF_') and not raw.startswith((b'#\\#CIF_1.1', b'#\\#CIF_1.0')):
        raise ValueError('Cairystal attribution helper supports CIF1 only')
    doc = gemmi.cif.read_string(raw.decode('ascii'))
    if not len(doc): raise ValueError('CIF attribution requires a parsed data block')
    before = snapshot(doc)
    lines = raw.splitlines(keepends=True)
    existing = False
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith(b'#'): break
        if stripped == CAIRYSTAL_COMMENT: existing = True
    offset = len(lines[0]) if raw.startswith(b'#\\#CIF_') else 0
    eol = re.search(rb'\r\n|\r|\n', raw)
    insertion = CAIRYSTAL_COMMENT + (eol.group() if eol else b'\n')
    candidate = raw if existing else raw[:offset] + insertion + raw[offset:]
    if snapshot(gemmi.cif.read_string(candidate.decode('ascii'))) != before:
        raise ValueError('CIF attribution changed parsed data')
    record = {'source_sha256':sha(path), 'status':'already_present' if existing else 'added',
              'comment':CAIRYSTAL_COMMENT.decode('ascii'), 'all_cif_values_unchanged':True,
              'original_bytes_preserved':True, 'insertion_byte_offset':None if existing else offset}
    if not existing:
        if candidate[:offset] + candidate[offset+len(insertion):] != raw:
            raise ValueError('CIF attribution changed original bytes')
        backup = audit_path.with_suffix('.before.cif')
        if backup.exists(): raise ValueError('CIF attribution backup already exists')
        backup.write_bytes(raw)
        path.write_bytes(candidate)
        record['original_file'] = str(backup)
    record['output_sha256'] = sha(path)
    write_json(audit_path, record)
    return record

def check_ascii(path):
    raw = Path(path).read_bytes()
    bad = [(i, b) for i, b in enumerate(raw) if b > 126 or (b < 32 and b not in (9, 10, 13))]
    if bad:
        i, b = bad[0]
        line = raw[:i].count(b'\n') + 1
        raise ValueError(f'CIF1 character preflight failed at line {line}, byte {i}: 0x{b:02x}; no upload performed. Preserve the source and review non-ASCII/control text.')
    return {'ascii_printable': True, 'sha256': sha(path)}

def encode_narratives(path, audit_path):
    """Only two prose scalars may change; never rewrite model labels or data to pass."""
    path, audit_path = Path(path), Path(audit_path)
    raw = path.read_bytes(); doc = gemmi.cif.read_string(raw.decode('utf-8'))
    before = snapshot(doc); changes = []
    for block in doc:
        for tag in sorted(NARRATIVE_TAGS):
            token = block.find_value(tag)
            if not token or token in ('?', '.'): continue
            text = gemmi.cif.as_string(token)
            if text.isascii(): continue
            # Reversible JSON string notation is explicitly labeled, not a chemical transliteration.
            encoded = 'Original Unicode narrative as a JSON string with Unicode escapes; exact UTF-8 text is in the accompanying audit record:\n' + json.dumps(text, ensure_ascii=True)
            block.set_pair(tag, gemmi.cif.quote(encoded))
            changes.append({'block': block.name, 'tag': tag, 'original_utf8': text, 'encoded': encoded})
    after = snapshot(doc)
    changed_keys = {(x['block'], x['tag']) for x in changes}
    if any(after[name].get(tag) != value for name, fields in before.items() for tag, value in fields.items() if (name, tag) not in changed_keys):
        raise ValueError('CIF text preflight changed protected tokens')
    # Fail without changing the candidate when non-ASCII remains outside prose.
    candidate = doc.as_string().encode('utf-8') if changes else raw
    bad = [b for b in candidate if b > 126 or (b < 32 and b not in (9, 10, 13))]
    record = {'source_sha256': sha(path), 'changes': changes, 'protected_tokens_unchanged': True}
    if bad:
        record['status'] = 'blocked_non_narrative_characters'; write_json(audit_path, record)
        raise ValueError('Non-ASCII/control characters remain outside supported narrative scalars; candidate unchanged and upload blocked')
    if changes:
        backup = audit_path.with_suffix('.original.cif')
        if backup.exists(): raise ValueError('CIF preflight backup already exists')
        backup.write_bytes(raw); path.write_bytes(candidate); record['original_file'] = str(backup)
    record.update(status='ready', **check_ascii(path)); write_json(audit_path, record)
    return record
