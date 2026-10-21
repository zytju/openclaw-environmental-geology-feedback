"""Chinese reading views of validated records; no second model call."""
import html
import re
from .contracts import DIMENSIONS, LABELS

STATES={'supported':'达到基本要求','partial':'需修订','absent':'内容缺失','needs_teacher':'待教师核查','not_in_scope':'本轮不评'}
VERDICTS={'aligned':'依据一致','suspect':'需调整','omitted':'有遗漏','needs_teacher':'待人工核查'}
DISPOSITIONS={'accept_proposal':'可进入教师终审','revise_feedback':'调整后再审','hold':'暂缓发放'}
SOURCE_NAMES={'ZOU2021':'Zou等2021','WEN2017':'Wen等2017','NCDC2020':'国家冰川冻土沙漠科学数据中心2020'}


def md(value):
    return re.sub(r'([\\`*_{}\[\]()#+.!|>\-])',r'\\\1',html.escape(str(value),quote=False))


def _status(final_record):
    if final_record is None:return '待教师终审'
    return '教师已采用' if final_record['approved_for_release'] else '教师已终审，暂缓发放'


def _sources(citations):
    seen=set();lines=[]
    for item in citations:
        pair=(item['source_id'],item['locator'])
        if pair in seen:continue
        seen.add(pair)
        lines+=['来源：'+md(SOURCE_NAMES.get(pair[0],pair[0]))+'，'+md(pair[1])+'。','']
    return lines


def _location(anchor):
    if anchor['paragraph_id']=='REPORT':return []
    return ['原文 '+md(anchor['paragraph_id'])+'：'+md(anchor['quote']),'']


def _issue(issue, compact=False):
    priority={'major':'主要问题','minor':'次要问题','teacher_check':'待教师核查'}[issue['severity']]
    lines=['### '+md(issue['issue_id'])+' '+priority,'']+_location(issue['anchor'])
    seen=set()
    for label,key in [('问题','problem'),('依据','rationale'),('下一步','revision_action'),('核查问题','check_question'),('资料与判断限制','uncertainty')]:
        if compact and key not in ('problem','revision_action'):continue
        value=issue[key].strip()
        if value and value not in seen:lines+=[label+'：'+md(value),''];seen.add(value)
    return lines+_sources(issue['citations'])


def feedback_markdown(record, simulated=False, *, final_record=None, compact=False, submission=None):
    """final_record must already pass finalize.bound_decision at the caller."""
    selected=None if final_record is None else set(final_record['released_issue_ids'])
    student_issues=[i for d in record['dimensions'] for i in d['issues'] if i['severity']!='teacher_check' and (selected is None or i['issue_id'] in selected)]
    lines=['# 案例报告反馈','',md(record['student_id'])+' · '+('教学演示 · ' if simulated else '')+_status(final_record),'']
    if final_record is not None and not final_record['approved_for_release']:
        lines+=['本轮反馈暂缓发放，以下内容供教师核查。','']
    if submission is not None and submission['stage']=='revision':
        decisions={'adopt':'采纳','partly_adopt':'部分采纳','reject':'拒绝'}
        counts=[str(sum(r['decision']==key for r in submission['revisions']))+'项'+label
                for key,label in decisions.items() if any(r['decision']==key for r in submission['revisions'])]
        lines+=['提交的修订说明：'+'，'.join(counts)+'。','']
    lines+=['本轮有'+str(len(student_issues))+'项修订任务。' if student_issues else '本轮没有需要逐项回应的修订任务。','','| 评价维度 | 本轮判断 |','|---|---|']
    for d,label in zip(record['dimensions'],LABELS):lines+=['| '+label+' | '+STATES[d['assessment']]+' |']
    lines+=[''];teacher_only=[]
    for d,label in zip(record['dimensions'],LABELS):
        if d['assessment']=='not_in_scope':continue
        if not compact:lines+=['## '+label,'',md(d['basis']),'']+_sources(d['citations'])
        for issue in d['issues']:
            if issue['severity']=='teacher_check':teacher_only.append(issue)
            elif selected is None or issue['issue_id'] in selected:lines+=_issue(issue,compact)
    if teacher_only and final_record is None:
        lines+=['## 待教师核查','']
        for issue in teacher_only:lines+=_issue(issue,compact)
    if not compact:lines+=['模型原件说明：'+md(record['boundary_reminder']),'']
    lines+=['以上为形成性反馈建议，待教师复核。' if final_record is None else '本页采用状态依据本轮教师终审记录；本地生成不代表学生已经收到。','']
    return '\n'.join(lines)


def _teacher_edit_lines(ledger):
    labels=dict(zip(DIMENSIONS,LABELS));actions={'replace_issue':'改写问题','add_issue':'新增问题','remove_issue':'撤回问题','set_dimension':'调整维度'}
    lines=['## 教师修改记录','']
    for n,entry in enumerate(ledger['history'],1):
        plan=entry['plan'];levels={d['dimension']:d['level_proposal'] for d in entry['before_feedback']['dimensions']}
        lines+=['修改'+str(n)+' · '+md(plan['reviewer_code'])+' · '+md(plan['reviewed_at']),'']
        if plan['reviewer_code']=='T000':lines+=['T000为合成测试身份。','']
        for op in plan['operations']:
            detail=labels[op['dimension']]+'：'+actions[op['op']]
            issue_id=op.get('issue_id') or (op.get('value') or {}).get('issue_id')
            if issue_id:detail+=' '+issue_id
            if op['op']=='set_dimension' and 'level_proposal' in op['value']:
                old,new=levels[op['dimension']],op['value']['level_proposal']
                show=lambda v:'本轮不评' if v is None else str(v)+'级'
                detail+='，'+show(old)+' → '+show(new);levels[op['dimension']]=new
            lines+=[md(detail)+'。','','理由：'+md(op['reason']),'']
    return lines


def teacher_markdown(record, simulated=False, *, feedback=None, final_record=None, compact=False, edit_ledger=None):
    levels={d['dimension']:d['level_proposal'] for d in feedback['dimensions']} if feedback else {}
    outside={d['dimension'] for d in feedback['dimensions'] if d['assessment']=='not_in_scope'} if feedback else set()
    lines=['# 案例报告反馈复核','',md(record['student_id'])+' · '+('教学演示 · ' if simulated else '')+_status(final_record),'']
    if final_record is None or record['disposition']!='accept_proposal':lines+=['模型处置建议：'+DISPOSITIONS[record['disposition']]+'。','']
    lines+=['| 评价维度 | 核查结论 |','|---|---|']
    for check,label in zip(record['checks'],LABELS):
        value='本轮不评' if check['dimension'] in outside else VERDICTS[check['verdict']]
        if levels.get(check['dimension']) is not None:value+='，建议'+str(levels[check['dimension']])+'级'
        lines+=['| '+label+' | '+value+' |']
    lines+=['']
    for check,label in zip(record['checks'],LABELS):
        if compact and check['dimension'] in outside:continue
        if not compact or check['verdict']!='aligned':lines+=['## '+label,'',md(check['reason']),'']+_location(check['anchor'])+_sources(check['citations'])
        elif levels.get(check['dimension']) is not None and levels[check['dimension']]<3:
            lines+=[label+'：'+md(check['reason']),'']
    if record['omissions']:
        lines+=['## 需要补充的反馈','']
        for item in record['omissions']:lines+=[md(item['problem']),'','核查行动：'+md(item['suggested_check']),'']+_location(item['anchor'])+_sources(item['citations'])
    if record['teacher_questions']:
        lines+=['## 待教师决定','']+['- '+md(q) for q in record['teacher_questions']]+['']
    if compact and all(c['verdict']=='aligned' for c in record['checks']) and not record['omissions'] and not record['teacher_questions']:
        lines+=['本轮未发现需要调整的反馈、遗漏项或新增核查事项。','']
    if edit_ledger:lines+=_teacher_edit_lines(edit_ledger)
    if final_record is None:lines+=['教师核对后决定是否采用和发放。','']
    else:
        lines+=['人工终审时间：'+md(final_record['reviewed_at'])+'。','']
        if not compact or record['disposition']!='accept_proposal':lines+=[md(final_record['comment']),'']
    return '\n'.join(lines)


def released_markdown(record):
    labels=dict(zip(DIMENSIONS,LABELS))
    lines=['# 教师核对后的反馈','',md(record['student_id'])+' · '+('教学演示 · ' if record['is_simulated'] else '')+'教师已采用','']
    for item in record['issues']:lines+=['## '+labels[item['dimension']],'']+_issue(item['issue'])
    if not record['issues']:lines+=['本次没有发放需要逐项回应的修订问题。','']
    lines+=['请依据证据自主修订，可以有理由地部分采纳或拒绝建议。','']
    return '\n'.join(lines)
