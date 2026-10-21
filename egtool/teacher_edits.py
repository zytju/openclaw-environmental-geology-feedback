"""Versioned teacher corrections; original model output and every edit remain readable."""
import copy
import datetime as dt
import re
from pathlib import Path
from .contracts import require, read_json, digest, check_feedback, material_gate, PII, prose_text
from .pipeline import assets, save, save_text
from .intake import private_output
from .render import feedback_markdown


def _apply(feedback, operations, previous_ids=()):
    value = copy.deepcopy(feedback)
    require(isinstance(operations, list) and 1 <= len(operations) <= 40, 'EDIT_OPERATIONS_REQUIRED')
    used = set(previous_ids) | {i['issue_id'] for d in value['dimensions'] for i in d['issues']}
    for op in operations:
        require(isinstance(op, dict) and set(op) <= {'op','dimension','issue_id','value','reason'}, 'EDIT_OPERATION_FIELDS')
        require(isinstance(op.get('reason'), str) and 10 <= len(op['reason'].strip()) <= 1000, 'EDIT_REASON_REQUIRED')
        dims = [d for d in value['dimensions'] if d['dimension'] == op.get('dimension')]
        require(len(dims) == 1, 'EDIT_DIMENSION_UNKNOWN')
        d = dims[0]; kind = op.get('op')
        if kind == 'set_dimension':
            require(isinstance(op.get('value'), dict) and bool(op['value']) and
                set(op['value']) <= {'assessment','level_proposal','basis','anchor','evidence_card_ids','citations','related_issue_ids'}, 'EDIT_DIMENSION_FIELDS')
            d.update(copy.deepcopy(op['value']))
        elif kind == 'add_issue':
            issue = op.get('value'); require(isinstance(issue,dict) and issue.get('issue_id') not in used, 'EDIT_ISSUE_ID_REUSED')
            used.add(issue.get('issue_id'));d['issues'].append(copy.deepcopy(issue))
        elif kind in ('replace_issue','remove_issue'):
            found = [i for i,x in enumerate(d['issues']) if x['issue_id'] == op.get('issue_id')]
            require(len(found) == 1, 'EDIT_ISSUE_UNKNOWN')
            if kind == 'remove_issue':d['issues'].pop(found[0])
            else:
                require(isinstance(op.get('value'),dict) and op['value'].get('issue_id') == op['issue_id'], 'EDIT_ISSUE_ID_CHANGED')
                d['issues'][found[0]] = copy.deepcopy(op['value'])
        else:require(False, 'EDIT_OPERATION_UNKNOWN')
    return value


def _check_plan(plan, sub, feedback, review_sha=None):
    required = {'edit_version','student_id','submission_sha256','feedback_sha256','teacher_review_sha256',
                'reviewer_code','reviewed_at','operations'}
    require(isinstance(plan,dict) and set(plan) == required and plan['edit_version'] == '1.0.0', 'EDIT_PLAN_FIELDS')
    require(plan['student_id'] == sub['student_id'] and plan['submission_sha256'] == digest(sub), 'EDIT_SUBMISSION_BINDING')
    require(plan['feedback_sha256'] == digest(feedback), 'EDIT_FEEDBACK_BINDING')
    require(review_sha is None or plan['teacher_review_sha256'] == review_sha, 'EDIT_REVIEW_BINDING')
    require(bool(re.fullmatch(r'T[0-9]{3}',plan['reviewer_code'])), 'EDIT_REVIEWER_CODE')
    require(sub['material_kind'] == 'synthetic' or plan['reviewer_code'] != 'T000', 'REAL_REVIEWER_REQUIRED')
    try:t=dt.datetime.fromisoformat(plan['reviewed_at'])
    except (ValueError,TypeError):raise ValueError('EDIT_TIME_REQUIRED')
    require(t.tzinfo is not None,'EDIT_TIMEZONE_REQUIRED')
    require(not PII.search(prose_text(plan)),'EDIT_POSSIBLE_PERSONAL_INFORMATION')


def _amended(feedback,plan,previous_ids=()):
    value=_apply(feedback,plan['operations'],previous_ids)
    value['teacher_edit_trace_id']=digest({'source_feedback_sha256':digest(feedback),'plan':plan})
    return value


def resolve_ledger(feedback_path,feedback,provided=None):
    if provided:return Path(provided)
    if 'teacher_edit_trace_id' in feedback:
        p=Path(feedback_path).parent/'edit-ledger.json'
        require(p.is_file(),'EDIT_LEDGER_REQUIRED')
        return p
    return None


def verify_ledger(path, sub, feedback, intake=None):
    ledger=read_json(path)
    require(set(ledger)=={'edit_version','student_id','submission_sha256','effective_feedback_sha256','history'},'EDIT_LEDGER_FIELDS')
    require(ledger['edit_version']=='1.0.0' and ledger['student_id']==sub['student_id'] and ledger['submission_sha256']==digest(sub),'EDIT_LEDGER_SUBMISSION')
    history=ledger['history'];require(isinstance(history,list) and bool(history),'EDIT_HISTORY_EMPTY')
    parent=None;previous=None;known_ids=set()
    for item in history:
        require(set(item)=={'before_feedback','after_feedback','plan','previous_entry_sha256','entry_sha256'},'EDIT_HISTORY_FIELDS')
        require(item['previous_entry_sha256']==parent,'EDIT_HISTORY_PARENT')
        require(item['entry_sha256']==digest({k:v for k,v in item.items() if k!='entry_sha256'}),'EDIT_HISTORY_HASH')
        require(previous is None or item['before_feedback']==previous,'EDIT_HISTORY_CONTINUITY')
        _check_plan(item['plan'],sub,item['before_feedback'])
        require(_amended(item['before_feedback'],item['plan'],known_ids)==item['after_feedback'],'EDIT_HISTORY_REPLAY')
        if intake is not None:
            schemas,sources,facts=assets()
            for fb in (item['before_feedback'],item['after_feedback']):
                check_feedback(fb,sub,material_gate(sub,intake,sources),schemas['feedback'],facts)
        for fb in (item['before_feedback'],item['after_feedback']):known_ids.update(i['issue_id'] for d in fb['dimensions'] for i in d['issues'])
        parent=item['entry_sha256'];previous=item['after_feedback']
    require(previous==feedback and ledger['effective_feedback_sha256']==digest(feedback),'EDIT_LEDGER_EFFECTIVE_FEEDBACK')
    return ledger


def edit_template(submission,intake,feedback,review,out):
    from .finalize import context
    sub,fb,tr,_=context(submission,intake,feedback,review)
    private_output(out,sub)
    plan={'edit_version':'1.0.0','student_id':sub['student_id'],'submission_sha256':digest(sub),
          'feedback_sha256':digest(fb),'teacher_review_sha256':digest(tr),'reviewer_code':'T000',
          'reviewed_at':'NOT_REVIEWED','operations':[]}
    save(out,plan);return Path(out)


def apply_edits(submission,intake,feedback,review,plan,out,previous_ledger=None):
    from .finalize import context
    sub,fb,tr,schemas=context(submission,intake,feedback,review);it=read_json(intake)
    plan=read_json(plan);_check_plan(plan,sub,fb,digest(tr))
    previous_ledger=resolve_ledger(feedback,fb,previous_ledger)
    history=verify_ledger(previous_ledger,sub,fb,it)['history'] if previous_ledger else []
    previous_ids={i['issue_id'] for entry in history for snap in ('before_feedback','after_feedback') for d in entry[snap]['dimensions'] for i in d['issues']}
    value=_amended(fb,plan,previous_ids);_,sources,facts=assets()
    check_feedback(value,sub,material_gate(sub,it,sources),schemas['feedback'],facts)
    entry={'before_feedback':fb,'after_feedback':value,'plan':plan,
           'previous_entry_sha256':history[-1]['entry_sha256'] if history else None}
    entry['entry_sha256']=digest(entry)
    ledger={'edit_version':'1.0.0','student_id':sub['student_id'],'submission_sha256':digest(sub),
            'effective_feedback_sha256':digest(value),'history':history+[entry]}
    private_output(out,sub);out=Path(out);require(not out.exists(),'OUTPUT_EXISTS');out.mkdir(parents=True,mode=0o700)
    save(out/'model-feedback-original.json',fb);save(out/'model-review-original.json',tr)
    save(out/'feedback-amended.json',value);save(out/'edit-ledger.json',ledger)
    save_text(out/'feedback-amended.md',feedback_markdown(value,sub['material_kind']=='synthetic'))
    save_text(out/'edit-summary.txt','教师修改记录\n'+''.join(f"{n}. {x['op']} {x['dimension']} {x.get('issue_id','')}：{x['reason']}\n" for n,x in enumerate(plan['operations'],1))+
              '\n修改稿尚未终审。须对修改稿重新复核，并生成绑定修改稿和修改记录的新终审表。\n')
    return out
