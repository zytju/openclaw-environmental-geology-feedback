"""Render validated records for teachers without activating links from input."""
import html
import re
from .contracts import DIMENSIONS, LABELS


def md(value):
    return re.sub(r'([\\`*_{}\[\]()#+.!|>\-])',r'\\\1',html.escape(str(value),quote=False))


def feedback_markdown(record, simulated=False):
    lines=[f"# {record['student_id']} 案例报告形成性反馈",'',
           '模拟技术运行输出，不能作为真实课堂反馈。' if simulated else 'AI反馈草稿，教师终审后发放。',
           '',f"提交校验值：`{record['submission_sha256']}`",'']
    for d,label in zip(record['dimensions'],LABELS):
        level='待教师判断' if d['level_proposal'] is None else str(d['level_proposal'])+'（仅建议）'
        lines.extend([f'## {label}','',f'等级：{level}。', '',md(d['basis']),''])
        if d['anchor']['quote'] is not None:
            lines.extend([f"原文位置：{d['anchor']['paragraph_id']}。",'',md(d['anchor']['quote']),''])
        for issue in d['issues']:
            severity={'major':'主要问题','minor':'次要问题','teacher_check':'仅供教师核查'}[issue['severity']]
            lines.extend([f"### {issue['issue_id']} {severity}",'',
                '**问题与证据缺口：** '+md(issue['problem']),'',
                '**推理与判断依据：** '+md(issue['rationale']),'',
                '**修订动作：** '+md(issue['revision_action']),'',
                '**核查问题：** '+md(issue['check_question']),'',
                '**不确定性：** '+md(issue['uncertainty']),''])
            for c in issue['citations']:
                lines.extend([f"来源：{md(c['claim_id'])} / {md(c['source_id'])} / {md(c['locator'])}",''])
        for c in d['citations']:
            lines.extend([f"本维度来源：{md(c['claim_id'])} / {md(c['source_id'])} / {md(c['locator'])}",''])
    lines.extend(['## 边界提醒','',md(record['boundary_reminder']),''])
    return '\n'.join(lines)


def released_markdown(record):
    labels=dict(zip(DIMENSIONS,LABELS))
    lines=[f"# {record['student_id']} 教师核对后的反馈",'',
        '模拟演练，不能作为真实课堂记录。' if record['is_simulated'] else '请依据证据自主修订；可以有理由地拒绝建议。','']
    for item in record['issues']:
        issue=item['issue']
        lines += [f"## {issue['issue_id']} {labels[item['dimension']]}",'',
            '问题：'+md(issue['problem']),'','依据：'+md(issue['rationale']),'',
            '下一步：'+md(issue['revision_action']),'','核查问题：'+md(issue['check_question']),'',
            '不确定性：'+md(issue['uncertainty']),'']
        if issue['anchor']['quote'] is not None:
            lines += ['原文 '+md(issue['anchor']['paragraph_id'])+'：'+md(issue['anchor']['quote']),'']
        for c in issue['citations']:
            lines += ['来源：'+md(c['claim_id'])+' / '+md(c['source_id'])+' / '+md(c['locator']),'']
    if not record['issues']:
        lines += ['本次没有发放需要逐项回应的修订问题。','']
    return '\n'.join(lines)


def teacher_markdown(record,simulated=False):
    lines=[f"# {record['student_id']} 教师端反馈复核草稿",'',
           '模拟技术输出，尚未进行专业终审。' if simulated else '教师端Agent的复核建议，待教师最终签认。','',
           '处置建议：'+md(record['disposition']),'']
    for x,label in zip(record['checks'],LABELS):
        lines.extend([f'## {label}','',md(x['verdict'])+'：'+md(x['reason']),''])
    if record['omissions']:
        lines.extend(['## 遗漏事项',''])
        for x in record['omissions']:lines.extend([md(x['problem']),md(x['suggested_check']),''])
    lines.extend(['## 请教师核实',''])
    for q in record['teacher_questions']:lines.extend([md(q),''])
    return '\n'.join(lines)
