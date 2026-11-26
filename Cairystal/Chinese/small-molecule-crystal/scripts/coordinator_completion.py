"""Reconcile a finished child pipeline; never run science, HTTP or report tools."""
from pathlib import Path

from crystal_runtime import sha, utc_now, write_json
from pipeline_intake import unlinked


def verified_pipeline_delivery(root, state, pipeline):
    import crystal_autorun as ar
    from delivery_contract import audit

    if pipeline.get('status') != 'complete' or pipeline.get('active_stage'):
        raise ValueError('Child pipeline has not completed')
    finish = unlinked(pipeline['finish_root'])
    finish.relative_to(root / 'pipeline')
    folder = finish / 'delivery_run'
    data = ar.read(folder / 'result.json')
    if data.get('status') != 'delivery_complete_needs_scientific_review':
        raise ValueError('Delivery has not passed final report/export review')
    contract = audit(folder, 'model')  # Read-only; keep sealed child evidence unchanged.
    if contract['status'] != 'artifacts_complete':
        raise ValueError('Delivery incomplete: ' + str(contract['missing_artifacts'] + contract['verification_issues']))
    receipt = ar.read(folder / 'customer_delivery.json')
    if receipt.get('status') != 'exported' or receipt != data.get('customer_delivery') or receipt != pipeline.get('customer_delivery'):
        raise ValueError('Customer export receipt does not match the completed pipeline')
    if unlinked(receipt['source_run']) != folder or unlinked(receipt['source_directory']) != folder / 'delivery':
        raise ValueError('Export receipt belongs to another delivery run')
    raw = unlinked(state['options']['data_dir'])
    target = unlinked(receipt['directory'])
    target.relative_to(raw / 'Cairystal')  # Repeated exports use Cairystal/运行_<timestamp>.
    if unlinked(receipt['data_directory']) != raw:
        raise ValueError('Export is not in this specimen Cairystal directory')
    if unlinked(pipeline['delivery']) != target:
        raise ValueError('Pipeline export directory differs')
    expected = ar.specimen_identity(root, state)['hkl_sha256']
    if not expected or data.get('inputs', {}).get('hkl') != expected or sha(unlinked(folder / 'delivery/model.hkl')) != expected:
        raise ar.WrongSpecimen('Delivered reflections differ from this task')
    hashes = receipt.get('exported_hashes', {})
    required = {'final_cif': 'model.cif', 'official_checkcif_pdf': 'IUCr_checkCIF.pdf',
                'word_zh': '晶体学报表_中文.docx', 'word_en': 'Crystallographic_Report_EN.docx'}
    if not set(contract['artifacts']) <= set(hashes):
        raise ValueError('Export hashes omit required deliverables')
    for name, digest in hashes.items():
        if Path(name).name != name or '/' in name or '\\' in name:
            raise ValueError('Invalid export filename')
        if sha(unlinked(target / name)) != digest:
            raise ValueError('Exported delivery changed: ' + name)
    for name in contract['artifacts']:
        if hashes[name] != sha(unlinked(folder / 'delivery' / name)):
            raise ValueError('Export is not the verified delivery: ' + name)
    for key, name in required.items():
        if unlinked(receipt['files'][key]) != target / name:
            raise ValueError('Customer file link differs from verified export')
    data['official_counts'] = contract['official_counts']
    return data


def reconcile(root, state, *, explicit=False):
    """Caller owns autorun.lock. Explicit repair may refresh an older finished job only."""
    import crystal_autorun as ar

    path = root / 'pipeline/pipeline.json'
    if state.get('native_branch') or not path.is_file():
        return False
    pipeline = ar.read(path)
    if pipeline.get('status') != 'complete':
        return False
    if state.get('pending') or (root / 'pipeline/pipeline.lock').exists():
        raise ValueError('A coordinator/pipeline action is still active or uncertain')
    if state.get('status') in {'cancelled', 'canceled'}:
        raise ValueError('Cancelled task is not adopted automatically')
    repaired_version = state.get('status') == 'complete' and state.get('completion_sync', {}).get('synchronizer_sha256') == ar.stamp()
    ar.verify(root, state, check_pipeline=False, check_version=not (explicit or repaired_version))
    data = verified_pipeline_delivery(root, state, pipeline)
    fingerprint = {str(p.relative_to(root)): sha(p) for p in [path, Path(pipeline['finish_root']) / 'delivery_run/result.json',
                                                             Path(pipeline['finish_root']) / 'delivery_run/customer_delivery.json']}
    if state.get('status') == 'complete' and state.get('completion_sync', {}).get('evidence') == fingerprint and repaired_version:
        if state.get('pipeline_seal') != ar.seal(root / 'pipeline'):
            raise ValueError('Completed pipeline changed after synchronization')
        return True
    history = root / 'completion_sync'
    history.mkdir(exist_ok=True)
    before = history / 'previous_autorun.json'
    if not before.exists():
        write_json(before, state)
    handoff = root / 'handoff.json'
    if handoff.is_file() and not (history / 'previous_handoff.json').exists():
        (history / 'previous_handoff.json').write_bytes(handoff.read_bytes())
    from workflow_observability import close_wait
    close_wait(state, 'complete')
    for key in ['reason', 'category', 'stopped_at', 'next_step']:
        state.pop(key, None)
    state.update(status='complete', finished_at=pipeline.get('finished_at') or data.get('finalized_at') or utc_now(),
                 delivery=data['customer_delivery']['directory'], customer_delivery=data['customer_delivery'],
                 customer_notice=data.get('customer_notice'), zip=data.get('zip'), official_counts=data['official_counts'])
    state['completion_sync'] = {'at': utc_now(), 'evidence': fingerprint, 'synchronizer_sha256': ar.stamp(),
                                'explicit_repair': explicit, 'previous_state': str(before),
                                'scope': 'Delivery state only; no solution, refinement, upload or report generation.'}
    state['pipeline_seal'] = ar.seal(root / 'pipeline')
    ar.save(root, state)
    if handoff.is_file():
        write_json(handoff, {'status': 'resolved', 'resolved_at': state['completion_sync']['at'],
                             'reason': 'Verified child delivery completed', 'previous_handoff': str(history / 'previous_handoff.json'),
                             'delivery': state['delivery']})
    return True


def notify_parent(pipeline_root):
    """Best-effort callback after releasing the child lock; resume/status also reconcile."""
    import crystal_autorun as ar

    root = pipeline_root.parent
    if pipeline_root.name != 'pipeline' or not (root / 'autorun.json').is_file():
        return
    # The normal coordinator owns this lock while its child runs. It will refresh on return.
    if (root / 'autorun.lock').exists():
        return
    try:
        with ar.lock(root):
            state = ar.read(root / 'autorun.json')
            if reconcile(root, state):
                ar.publish(root, state)
    except Exception as exc:
        # Do not turn a successful scientific delivery into a failed child command.
        # Keep the issue visible and recoverable via autorun sync-delivery/status/resume.
        write_json(root / 'completion_sync_error.json', {'at': utc_now(), 'error': str(exc),
                   'next_tool': 'autorun sync-delivery --run CURRENT_JOB', 'delivery_not_modified': True})
