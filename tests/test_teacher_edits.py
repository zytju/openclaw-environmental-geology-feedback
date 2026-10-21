import copy
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from egtool.contracts import digest,read_json,ContractError
from egtool.pipeline import MockBackend,mock_submission,mock_intake,save
from egtool.finalize import final_template,release,context
from egtool.teacher_edits import apply_edits,verify_ledger


class TeacherEditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name)
        self.sub=mock_submission();self.fb=MockBackend().generate('student',self.sub)
        self.tr=MockBackend().generate('teacher',self.sub,self.fb)
        self.it=mock_intake(self.sub)
        for n,v in [('sub',self.sub),('intake',self.it),('fb',self.fb),('tr',self.tr)]:save(self.p/(n+'.json'),v)
        self.args=[self.p/(n+'.json') for n in ('sub','intake','fb','tr')]
        self.issue=copy.deepcopy(self.fb['dimensions'][0]['issues'][0]);self.issue['revision_action']='先核对原文是否作出该判断，再补充与原文对应的依据。'
        self.plan={'edit_version':'1.0.0','student_id':'S001','submission_sha256':digest(self.sub),
            'feedback_sha256':digest(self.fb),'teacher_review_sha256':digest(self.tr),'reviewer_code':'T000',
            'reviewed_at':'2026-10-21T21:30:00+08:00','operations':[{'op':'replace_issue','dimension':'problem_identification',
            'issue_id':'I01','value':self.issue,'reason':'合成技术测试中改写行动建议，保留问题编号和原文位置。'}]}
    def tearDown(self):self.tmp.cleanup()
    def run_edit(self):
        (self.p/'plan.json').write_text(json.dumps(self.plan));return apply_edits(*self.args,self.p/'plan.json',self.p/'edited')
    def test_original_is_unchanged_and_ledger_replays(self):
        before=[p.read_bytes() for p in self.args];out=self.run_edit();fb=read_json(out/'feedback-amended.json')
        self.assertEqual(before,[p.read_bytes() for p in self.args]);self.assertNotEqual(digest(fb),digest(self.fb))
        ledger=verify_ledger(out/'edit-ledger.json',self.sub,fb,self.it)
        self.assertEqual(ledger['history'][0]['before_feedback'],self.fb)
        self.assertEqual(ledger['history'][0]['plan']['operations'][0]['reason'],self.plan['operations'][0]['reason'])
        from egtool.display import reading_views
        tr=MockBackend().generate('teacher',self.sub,fb);save(self.p/'new-review.json',tr)
        views=reading_views(self.args[0],self.args[1],out/'feedback-amended.json',self.p/'new-review.json',self.p/'reading')
        teacher=next(views.glob('*.teacher-reading_*.md')).read_text();student=next(views.glob('*.student-reading_*.md')).read_text()
        self.assertIn('教师修改记录',teacher);self.assertIn('改写问题 I01',teacher)
        self.assertIn(self.plan['operations'][0]['reason'],teacher);self.assertIn('T000为合成测试身份',teacher)
        self.assertNotIn('教师修改记录',student)
    def test_stale_review_is_rejected_for_amended_feedback(self):
        out=self.run_edit()
        with self.assertRaisesRegex(ContractError,'TEACHER_FEEDBACK_MISMATCH'):
            context(self.args[0],self.args[1],out/'feedback-amended.json',self.args[3])
    def test_tampered_reason_is_detected(self):
        out=self.run_edit();p=out/'edit-ledger.json';v=read_json(p);v['history'][0]['plan']['operations'][0]['reason']='更改后的修改原因，原有校验值应当立即失效。';p.write_text(json.dumps(v))
        with self.assertRaisesRegex(ContractError,'EDIT_HISTORY_HASH'):verify_ledger(p,self.sub,read_json(out/'feedback-amended.json'))
    def test_wrong_original_feedback_is_rejected(self):
        self.plan['feedback_sha256']='0'*64
        with self.assertRaisesRegex(ContractError,'EDIT_FEEDBACK_BINDING'):self.run_edit()
        self.assertFalse((self.p/'edited').exists())
    def test_reason_and_timestamp_are_required(self):
        self.plan['reviewed_at']='NOT_REVIEWED'
        with self.assertRaisesRegex(ValueError,'EDIT_TIME_REQUIRED'):self.run_edit()
    def test_fabricated_quote_cannot_be_added(self):
        self.plan['operations'][0]['value']['anchor']['quote']='原文完全没有出现过的引文'
        with self.assertRaises(ContractError):self.run_edit()
    def test_original_issue_id_cannot_be_reused_after_removal(self):
        self.plan['operations']=[{'op':'remove_issue','dimension':'problem_identification','issue_id':'I01','reason':'测试删除旧问题后，是否可以冒用原问题编号重新新增。'},
            {'op':'add_issue','dimension':'problem_identification','value':self.issue,'reason':'新增测试项目仍使用原编号，应拒绝以防丢失问题身份。'}]
        with self.assertRaisesRegex(ContractError,'EDIT_ISSUE_ID_REUSED'):self.run_edit()
    def test_new_final_binds_ledger_and_remains_unsigned(self):
        out=self.run_edit();fb=read_json(out/'feedback-amended.json');tr=MockBackend().generate('teacher',self.sub,fb)
        save(self.p/'new-review.json',tr)
        final_template(self.args[0],self.args[1],out/'feedback-amended.json',self.p/'new-review.json',self.p/'unsigned.json',out/'edit-ledger.json')
        rec=read_json(self.p/'unsigned.json');self.assertFalse(rec['human_review_complete'])
        self.assertEqual(rec['edit_ledger_sha256'],digest(read_json(out/'edit-ledger.json')))
        with self.assertRaisesRegex(ContractError,'HUMAN_REVIEW_NOT_COMPLETE'):
            release(self.args[0],self.args[1],out/'feedback-amended.json',self.p/'new-review.json',self.p/'unsigned.json',self.p/'release',out/'edit-ledger.json')
    def test_second_edit_retains_first_history(self):
        out=self.run_edit();fb=read_json(out/'feedback-amended.json');tr=MockBackend().generate('teacher',self.sub,fb);save(self.p/'review2.json',tr)
        plan=copy.deepcopy(self.plan);plan.update(feedback_sha256=digest(fb),teacher_review_sha256=digest(tr));plan['operations'][0]['value']['revision_action']='再次核对修改动作与原文的对应关系，并记录保留依据。';save(self.p/'plan2.json',plan)
        out2=apply_edits(self.args[0],self.args[1],out/'feedback-amended.json',self.p/'review2.json',self.p/'plan2.json',self.p/'edited2',out/'edit-ledger.json')
        ledger=verify_ledger(out2/'edit-ledger.json',self.sub,read_json(out2/'feedback-amended.json'),self.it)
        self.assertEqual(len(ledger['history']),2);self.assertEqual(ledger['history'][0],read_json(out/'edit-ledger.json')['history'][0])
    def test_marked_edit_cannot_lose_ledger_when_moved(self):
        out=self.run_edit();fb=read_json(out/'feedback-amended.json');tr=MockBackend().generate('teacher',self.sub,fb)
        save(self.p/'moved-feedback.json',fb);save(self.p/'moved-review.json',tr)
        with self.assertRaisesRegex(ContractError,'EDIT_LEDGER_REQUIRED'):
            final_template(self.args[0],self.args[1],self.p/'moved-feedback.json',self.p/'moved-review.json',self.p/'new-final.json')
    def test_final_template_automatically_binds_adjacent_edit_history(self):
        out=self.run_edit();fb=read_json(out/'feedback-amended.json');tr=MockBackend().generate('teacher',self.sub,fb);save(self.p/'new-review.json',tr)
        final_template(self.args[0],self.args[1],out/'feedback-amended.json',self.p/'new-review.json',self.p/'auto-final.json')
        self.assertEqual(read_json(self.p/'auto-final.json')['edit_ledger_sha256'],digest(read_json(out/'edit-ledger.json')))
    def test_additional_teacher_check_keeps_original_tasks(self):
        issue=copy.deepcopy(self.issue);issue['issue_id']='I90';issue['severity']='teacher_check'
        self.plan['operations']=[{'op':'add_issue','dimension':'problem_identification','value':issue,'reason':'测试补充教师核查事项，保留原有六项任务和已有评价依据。'}]
        out=self.run_edit();fb=read_json(out/'feedback-amended.json')
        self.assertEqual([i['issue_id'] for i in fb['dimensions'][0]['issues']],['I01','I90'])
        verify_ledger(out/'edit-ledger.json',self.sub,fb,self.it)
    def test_removal_requires_consistent_dimension_update(self):
        self.plan['operations']=[{'op':'remove_issue','dimension':'problem_identification','issue_id':'I01','reason':'合成技术测试中撤回已无依据的问题，并同步更新该维判断。'},
            {'op':'set_dimension','dimension':'problem_identification','value':{'assessment':'supported','level_proposal':2,'basis':'测试样例已满足本维基本要求，原问题已撤回。'},'reason':'原有问题撤回后，维度状态和理由应当与当前问题清单一致。'}]
        out=self.run_edit();fb=read_json(out/'feedback-amended.json');self.assertEqual(fb['dimensions'][0]['issues'],[])
        self.assertEqual(len(read_json(out/'edit-ledger.json')['history'][0]['plan']['operations']),2)
    def test_retired_issue_id_cannot_return_in_later_edit(self):
        self.plan['operations']=[{'op':'remove_issue','dimension':'problem_identification','issue_id':'I01','reason':'在首次修改中删除原问题，保留原问题身份供后续追溯。'},
            {'op':'set_dimension','dimension':'problem_identification','value':{'assessment':'supported','level_proposal':2,'basis':'测试中撤回原有问题并确认基本要求已满足。'},'reason':'问题撤回后同步调整维度判断，使当前评价与问题清单相符。'}]
        out=self.run_edit();fb=read_json(out/'feedback-amended.json');tr=MockBackend().generate('teacher',self.sub,fb);save(self.p/'review2.json',tr)
        plan=copy.deepcopy(self.plan);plan.update(feedback_sha256=digest(fb),teacher_review_sha256=digest(tr));plan['operations']=[{'op':'add_issue','dimension':'problem_identification','value':self.issue,'reason':'本次尝试复用已经删除的问题编号，程序应拒绝这项操作。'}];save(self.p/'plan2.json',plan)
        with self.assertRaisesRegex(ContractError,'EDIT_ISSUE_ID_REUSED'):
            apply_edits(self.args[0],self.args[1],out/'feedback-amended.json',self.p/'review2.json',self.p/'plan2.json',self.p/'edited2',out/'edit-ledger.json')

if __name__=='__main__':unittest.main()
