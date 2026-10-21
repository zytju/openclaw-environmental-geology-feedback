"""Explicit human review records, local release copies, and separate student counts."""
import copy
import csv
import datetime as dt
from pathlib import Path
from .contracts import (VERSION, DIMENSIONS, require, read_json, digest, validate,
    check_submission, material_gate, check_feedback, check_teacher, PII, prose_text)
from .pipeline import assets, save, save_text, stamp
from .intake import private_output
from .render import released_markdown


def context(submission, intake, feedback, review):
    schemas, sources, facts = assets()
    sub, it, fb, tr = map(read_json, [submission, intake, feedback, review])
    check_submission(sub, schemas['submission'], sources)
    validate(it, schemas['teacher-intake'])
    check_feedback(fb, sub, material_gate(sub, it, sources), schemas['feedback'], facts)
    check_teacher(tr, sub, fb, schemas['teacher-review'], facts)
    return sub, fb, tr, schemas


def final_template(submission, intake, feedback, review, out):
    sub, fb, tr, _ = context(submission, intake, feedback, review)
    private_output(out, sub)
    value = {'schema_version': VERSION, 'student_id': sub['student_id'], 'stage': sub['stage'],
        'material_kind': sub['material_kind'], 'assessed_dimensions': sub['assessed_dimensions'],
        'submission_sha256': digest(sub), 'feedback_sha256': digest(fb), 'teacher_review_sha256': digest(tr),
        'reviewer_code': 'T000', 'reviewed_at': 'NOT_REVIEWED', 'human_review_complete': False,
        'approved_for_release': False, 'released_issue_ids': [], 'confirmed_student_problem_dimensions': [],
        'comment': '待教师逐条核查并选择实际发放的问题；本模板不是终审完成记录。'}
    save(out, value)
    return Path(out)


def check_final(rec, schema):
    validate(rec, schema)
    require(1 <= int(rec['student_id'][1:]) <= 66, 'COHORT_ID_RANGE')
    require(rec['human_review_complete'], 'HUMAN_REVIEW_NOT_COMPLETE')
    require(not PII.search(prose_text(rec)), 'FINAL_POSSIBLE_PERSONAL_INFORMATION')
    require(set(rec['confirmed_student_problem_dimensions']) <= set(rec['assessed_dimensions']), 'FINAL_PROBLEM_OUTSIDE_SCOPE')
    if rec['material_kind'] == 'student_work':
        require(rec['reviewer_code'] != 'T000', 'REAL_REVIEWER_REQUIRED')
    try:
        reviewed = dt.datetime.fromisoformat(rec['reviewed_at'])
    except ValueError:
        raise ValueError('FINAL_REVIEW_ISO_DATETIME_REQUIRED')
    require(reviewed.tzinfo is not None, 'FINAL_REVIEW_TIMEZONE_REQUIRED')
    if not rec['approved_for_release']:
        require(not rec['released_issue_ids'], 'HELD_REVIEW_CANNOT_RELEASE_ISSUES')
    return rec


def bound_decision(sub, fb, tr, schemas, decisions):
    """Verify human status against this exact submission, feedback and review."""
    rec = check_final(read_json(decisions), schemas['teacher-final'])
    for key, expected in [('student_id', sub['student_id']), ('stage', sub['stage']),
        ('material_kind', sub['material_kind']), ('assessed_dimensions', sub['assessed_dimensions']),
        ('submission_sha256', digest(sub)), ('feedback_sha256', digest(fb)), ('teacher_review_sha256', digest(tr))]:
        require(rec[key] == expected, 'FINAL_BINDING_MISMATCH_' + key.upper())
    by_id = {i['issue_id']: i for d in fb['dimensions'] for i in d['issues']}
    require(set(rec['released_issue_ids']) <= by_id.keys(), 'FINAL_RELEASE_ISSUE_UNKNOWN')
    require(all(by_id[i]['severity'] != 'teacher_check' for i in rec['released_issue_ids']), 'TEACHER_ONLY_ISSUE_CANNOT_BE_RELEASED')
    if rec['approved_for_release'] and tr['disposition'] != 'accept_proposal':
        require(len(rec['comment'].strip()) >= 20, 'HUMAN_OVERRIDE_REASON_REQUIRED')
    return rec


def release(submission, intake, feedback, review, decisions, out):
    sub, fb, tr, schemas = context(submission, intake, feedback, review)
    rec = bound_decision(sub, fb, tr, schemas, decisions)
    private_output(out, sub)
    out = Path(out)
    require(not out.exists(), 'OUTPUT_EXISTS')
    out.mkdir(parents=True, mode=0o700)
    ts = stamp()
    save(out / (sub['student_id'] + '.final_' + ts + '.json'), rec)
    if rec['approved_for_release']:
        delivered = {'release_version': VERSION, 'student_id': sub['student_id'],
            'is_simulated': sub['material_kind'] == 'synthetic', 'final_record_sha256': digest(rec),
            'released_issue_ids': rec['released_issue_ids'], 'issues': [
                {'dimension': d['dimension'], 'issue': i} for d in fb['dimensions'] for i in d['issues']
                if i['issue_id'] in rec['released_issue_ids']]}
        validate(delivered, schemas['release'])
        save(out / (sub['student_id'] + '.released_' + ts + '.json'), delivered)
        save_text(out / (sub['student_id'] + '.released_' + ts + '.md'), released_markdown(delivered))
    return out


def summarize_finals(records, out, stage):
    schemas, _, _ = assets()
    p = Path(records)
    require(not p.is_symlink(), 'INPUT_DIRECTORY_SYMLINK')
    p = p.resolve(strict=True)
    files = sorted(p.rglob('*.final_*.json'))
    rows, seen = [], set()
    for f in files:
        current = f
        while current != p:
            require(not current.is_symlink(), 'SYMLINK_NOT_ALLOWED')
            current = current.parent
        rec = check_final(read_json(f), schemas['teacher-final'])
        if rec['stage'] != stage:
            continue
        require(rec['student_id'] not in seen, 'DUPLICATE_FINAL_STUDENT_STAGE')
        seen.add(rec['student_id']); rows.append(rec)
    require(1 <= len(rows) <= 66, 'FINAL_COUNT_1_TO_66')
    require(len({r['material_kind'] for r in rows}) == 1, 'MIXED_REAL_AND_SYNTHETIC_FINALS')
    for r in rows:
        private_output(out, r)
    out = Path(out)
    require(not out.exists(), 'OUTPUT_EXISTS')
    out.mkdir(parents=True, mode=0o700)
    summary = {'schema_version': VERSION, 'stage': stage, 'is_simulated': rows[0]['material_kind'] == 'synthetic',
        'human_final_reviews': len(rows), 'approved_feedback_packages': sum(r['approved_for_release'] for r in rows),
        'confirmed_beneficiaries': None, 'student_problem_counts': {}, 'scope_denominators': {},
        'caution': '人工填写的终审记录，不自动证明审查质量；已生成发放包不等于学生已收到。频数不是能力提升，不能代替参与记录和独立测评。'}
    for d in DIMENSIONS:
        summary['student_problem_counts'][d] = sum(d in r['confirmed_student_problem_dimensions'] for r in rows)
        summary['scope_denominators'][d] = sum(d in r['assessed_dimensions'] for r in rows)
    validate(summary, schemas['human-summary'])
    ts = stamp(); save(out / ('human-summary_' + ts + '.json'), summary)
    with (out / ('human-summary_' + ts + '.csv')).open('x', encoding='utf-8-sig', newline='') as f:
        import os
        os.chmod(f.name, 0o600)
        w = csv.writer(f);w.writerow(['dimension', 'teacher_confirmed_student_problem_count', 'scope_denominator', 'is_simulated'])
        for d in DIMENSIONS:
            w.writerow([d, summary['student_problem_counts'][d], summary['scope_denominators'][d], summary['is_simulated']])
    return summary
