"""Customer-facing explanations of factual workflow states; no scientific decisions."""
def next_step(category, upload_choice=None):
    """Assign an actual next action to the assistant or the sample owner."""
    if category == 'upload_authorization_required':
        if upload_choice == 'deny':
            return dict(owner='assistant', action='report_local_results', message='按本例已记录的选择提供本地结果。')
        if upload_choice == 'allow':
            return dict(owner='assistant', action='verify_existing_consent', message='核对已有授权对应的样品、文件和用途后，从上传步骤续接。')
        return dict(owner='user_if_no_prior_consent', action='check_consent_then_ask_once', message='助手先核对本例的既有授权。确实缺少授权时，只询问一次是否将最终 CIF 及结构因子提交 IUCr。')
    actions = {
        'chemical_graph_required': ('inspect_first_model', '助手先查看本例候选模型、电子密度和已有化学信息，比较元素与加氢方案。'),
        'scientific_decision': ('compare_local_models', '助手保留基线，用同一批反射比较有依据的候选，记录支持和反对各方案的证据。'),
        'solver_fallback_review': ('inspect_solver_output', '助手核对备用求解的日志与候选模型，继续可执行的局部精修。'),
        'report_review': ('review_reports', '助手查看未通过的报表检查，完成实际复核后从当前进度交付。'),
        'interrupted_action': ('recover_checkpoint', '助手先核对已有文件和回执，确认已完成的步骤再续接。'),
        'integrity_error': ('inspect_input_changes', '助手核对输入与版本指纹，保留原始记录。'),
    }
    action, message = actions.get(category, ('inspect_logs', '助手查看本步日志并处理可恢复的问题。'))
    return dict(owner='assistant', action=action, message=message)

def describe(state):
    status=state.get('status');category=state.get('category')
    if status=='complete':
        title='文件已生成，仍需核对科学结论'
        detail='请查看最终 CIF、官网 checkCIF PDF 和中英文 Word。文件齐全、精修收敛或没有 A/B 警告，都不能单独证明结构正确。'
        owner='研究者核对结论；助手说明未解决问题'
    elif status=='local_ready':
        title='本地处理完成，尚未完整交付'
        detail='本次选择了仅本地处理，官网报告和中英文 Word 尚未交付。请保留当前进度。'
        owner='助手按已记录的任务范围继续；不重复求解'
    else:
        messages={
          'chemical_graph_required':('已保留候选结构，需要判断化学组成','助手需依据本次电子密度、连接关系和已有化学信息判断元素及加氢。未知结构的用户无需编造 SMILES 或分子式。','助手先诊断；确实缺少关键背景时一次性说明'),
          'scientific_decision':('候选结构需要进一步判断','可能涉及空间群、原子指认、无序、加氢或 A/B 警告。当前模型还不是已确认的最终结构。','助手或晶体学人员复核'),
          'report_review':('模型或报告尚待复核','已有文件会保留；报告排版、数值或警告检查尚未全部通过。','助手检查具体未通过项目'),
          'upload_authorization_required':('本地结果已保留，等待官网上传选择','官网验证需要上传本次 CIF 和结构因子。若已经授权，助手应复用当前样品的授权记录并从此处继续。','仅未授权时需要用户选择'),
          'integrity_error':('检测到文件或版本变化','程序停止以避免混用不同版本的模型、数据或报告。原文件保留，助手需要核对变更。','助手核对文件来源'),
          'interrupted_action':('操作中断，结果需要确认','程序会先核对已经生成的文件或官网报告，不会盲目重复上传。','助手检查日志与恢复记录'),
          'execution_error':('本步骤未完成，正在等待排错','可能是输入格式、软件运行或环境问题，不能据此认定晶体解不出来。输入和日志已经保留。','助手先排错；不要要求用户解释专业报错')}
        title,detail,owner=messages.get(category,('处理中' if status in {'running','ready'} else '当前流程尚未完成','完成的步骤与耗时列在下方，详细日志单独保留。','助手继续处理'))
    if status == 'needs_attention':
        step = state.get('next_step') or next_step(category)
        owner = step['message']
        if category == 'upload_authorization_required' and step['action'] == 'report_local_results':
            title, detail = '本地结果已保留', '本例已选择仅在本地处理。'
    return {'title':title,'explanation':detail,'next_action_owner':owner,'scientific_correctness':'not_established_by_workflow_status'}
