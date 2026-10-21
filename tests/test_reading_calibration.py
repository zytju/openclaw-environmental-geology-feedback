import copy
import json
from pathlib import Path
import tempfile
import unittest
from egtool.calibration import blind_packet,evaluate
from egtool.contracts import ContractError,digest,read_json,DIMENSIONS
from egtool.display import reading_views
from egtool.finalize import final_template
from egtool.pipeline import ROOT,MockBackend,mock_submission,mock_intake,save
from egtool.render import feedback_markdown,teacher_markdown
from egtool.pipeline import stage,verify_profile
from egtool.runtime_audit import container_checks
from egtool.context_loader import bootstrap_context,verify_bootstrap,role_resources


class ReadingTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name)
        self.sub=mock_submission();self.fb=MockBackend().generate('student',self.sub)
        for d in self.fb['dimensions']:
            d.update(assessment='partial',level_proposal=1)
            d['issues'][0]['severity']='major'
        self.tr=MockBackend().generate('teacher',self.sub,self.fb)
        self.tr.update(disposition='accept_proposal',teacher_questions=[])
        for c in self.tr['checks']:c['verdict']='aligned'
        for name,value in [('sub',self.sub),('intake',mock_intake(self.sub)),('fb',self.fb),('tr',self.tr)]:save(self.p/(name+'.json'),value)
        self.args=[self.p/(name+'.json') for name in ['sub','intake','fb','tr']]
        final_template(*self.args,self.p/'unsigned.json')
        self.final=read_json(self.p/'unsigned.json')
        self.final.update(reviewer_code='T001',reviewed_at='2026-10-21T20:00:00+08:00',human_review_complete=True,
            approved_for_release=True,released_issue_ids=['I03'],confirmed_student_problem_dimensions=['reasoning_chain'],
            comment='合成测试中仅选择一个实际发放问题，其他草稿项不进入学生任务。')
    def tearDown(self):self.tmp.cleanup()
    def decisions(self):
        path=self.p/'final.json';path.write_text(json.dumps(self.final));return path
    def render(self,decisions=None):return reading_views(*self.args,self.p/'reading',decisions)

    def test_six_tasks_preserved_without_visual_count_limit(self):
        text=feedback_markdown(self.fb,True,compact=True)
        self.assertEqual(sum(('### I%02d'%i) in text for i in range(1,7)),6)
        for d in self.fb['dimensions']:
            issue=d['issues'][0]
            self.assertIn(issue['problem'],text);self.assertIn(issue['revision_action'],text)
    def test_reading_hides_hashes_and_machine_states(self):
        text=feedback_markdown(self.fb,True)+'\n'+teacher_markdown(self.tr,True,feedback=self.fb)
        self.assertNotIn(self.fb['submission_sha256'],text)
        for token in ['submission_sha256','accept_proposal','needs_teacher','aligned','partial']:self.assertNotIn(token,text)
        self.assertNotIn('建议1级',feedback_markdown(self.fb,True))
        self.assertIn('建议1级',teacher_markdown(self.tr,True,feedback=self.fb))
    def test_teacher_only_items_are_not_counted_as_student_tasks(self):
        self.fb['dimensions'][0]['issues'][0]['severity']='teacher_check'
        text=feedback_markdown(self.fb,True)
        self.assertIn('本轮有5项修订任务',text)
        self.assertIn('## 待教师核查',text)
        self.assertLess(text.index('## 待教师核查'),text.index('### I01'))
    def test_unsigned_view_does_not_claim_human_adoption(self):
        out=self.render();text='\n'.join(p.read_text() for p in out.glob('*.md'))
        self.assertIn('待教师终审',text);self.assertNotIn('教师已采用',text)
    def test_adopted_view_binds_final_and_releases_only_selected_tasks(self):
        out=self.render(self.decisions());student=next(out.glob('*.student-reading_*.md')).read_text()
        self.assertIn('教师已采用',student);self.assertIn('### I03',student)
        self.assertNotIn('### I01',student);self.assertNotIn('待教师复核',student)
        self.assertNotIn('已经发给学生',student)
    def test_hold_status_remains_hold(self):
        self.final.update(approved_for_release=False,released_issue_ids=[])
        out=self.render(self.decisions());text=next(out.glob('*.student-reading_*.md')).read_text()
        self.assertIn('暂缓发放',text);self.assertNotIn('教师已采用',text);self.assertNotIn('### I03',text)
    def test_old_feedback_final_cannot_change_current_status(self):
        self.final['feedback_sha256']='0'*64
        with self.assertRaisesRegex(ContractError,'FINAL_BINDING_MISMATCH_FEEDBACK'):self.render(self.decisions())
        self.assertFalse((self.p/'reading').exists())
    def test_previous_stage_adoption_cannot_approve_this_stage(self):
        self.final['stage']='revision'
        with self.assertRaisesRegex(ContractError,'FINAL_BINDING_MISMATCH_STAGE'):self.render(self.decisions())
    def test_unsigned_record_is_not_treated_as_final(self):
        with self.assertRaisesRegex(ContractError,'HUMAN_REVIEW_NOT_COMPLETE'):self.render(self.p/'unsigned.json')
    def test_altered_review_is_rejected_before_output(self):
        self.tr['feedback_sha256']='0'*64;(self.p/'tr.json').write_text(json.dumps(self.tr))
        with self.assertRaisesRegex(ContractError,'TEACHER_FEEDBACK_MISMATCH'):self.render()
        self.assertFalse((self.p/'reading').exists())
    def test_source_input_cannot_activate_html_or_markdown_links(self):
        self.fb['dimensions'][0]['basis']='<script>alert(1)</script> [打开](javascript:alert(1))'
        text=feedback_markdown(self.fb,True)
        self.assertNotIn('<script>',text);self.assertNotIn('[打开](',text)
    def test_out_of_scope_view_does_not_invent_missing_task(self):
        d=self.fb['dimensions'][-1];d.update(assessment='not_in_scope',level_proposal=None,issues=[],citations=[],evidence_card_ids=[])
        text=feedback_markdown(self.fb,True)
        self.assertIn('| 防治建议匹配 | 本轮不评 |',text)
        self.assertNotIn('## 防治建议匹配',text)
        teacher=teacher_markdown(self.tr,True,feedback=self.fb,compact=True)
        self.assertIn('| 防治建议匹配 | 本轮不评 |',teacher)
        self.assertNotIn('| 防治建议匹配 | 依据一致',teacher)
    def test_student_overview_hides_grades_inside_basis_but_retains_full_evidence(self):
        self.fb['dimensions'][0]['basis']='当前仍有对应证据缺口，因此建议等级1。'
        overview=feedback_markdown(self.fb,True,compact=True)
        evidence=feedback_markdown(self.fb,True)
        self.assertNotIn('建议等级1',overview);self.assertIn('建议等级1',evidence)
        self.assertIn(self.fb['dimensions'][0]['issues'][0]['revision_action'],overview)
    def test_teacher_overview_keeps_basis_for_level_below_highest(self):
        for d in self.fb['dimensions']:d['level_proposal']=3
        self.fb['dimensions'][3]['level_proposal']=2
        self.tr['checks'][3]['reason']='路径与条件已经对应，但没有比较多个情景或阻断环节，因此建议保持2级。'
        text=teacher_markdown(self.tr,True,feedback=self.fb,compact=True)
        self.assertIn('没有比较多个情景或阻断环节',text)


class CalibrationTest(unittest.TestCase):
    def setUp(self):self.suite=read_json(ROOT/'tests/fixtures/calibration_20261021_2036.json')
    def result(self):return {'results':[dict(case_id=x['case_id'],reason='仅供程序检查的测试结果，不是模型专业判断。',**x['expected']) for x in self.suite['cases']]}
    def test_blind_packet_removes_all_expected_answers(self):
        packet=blind_packet(self.suite)
        self.assertNotIn('expected',json.dumps(packet))
        self.assertEqual(len(packet['cases']),10)
        self.assertTrue(all('expected' in c for c in self.suite['cases']))
    def test_wrong_professional_decision_is_reported_as_failure(self):
        result=self.result();result['results'][0].update(decision='no_basis_for_criticism',level=None)
        report=evaluate(self.suite,result)
        self.assertFalse(report['all_passed']);self.assertEqual(report['passed'],9)
        self.assertFalse(report['checks'][0]['passed'])
    def test_duplicate_results_cannot_hide_an_omitted_case(self):
        result=self.result();result['results'][-1]=copy.deepcopy(result['results'][0])
        with self.assertRaisesRegex(ContractError,'CALIBRATION_DUPLICATE_RESULT'):evaluate(self.suite,result)
    def test_missing_case_is_not_counted_as_success(self):
        result=self.result();result['results'].pop()
        with self.assertRaisesRegex(ContractError,'CALIBRATION_CASE_SET_MISMATCH'):evaluate(self.suite,result)
    def test_blank_rationale_is_rejected(self):
        result=self.result();result['results'][0]['reason']=' '
        with self.assertRaises(ContractError):evaluate(self.suite,result)


class RuntimeBoundaryTest(unittest.TestCase):
    def test_role_policy_without_global_policy_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile=stage(Path(tmp)/'profile','legacy-list','provider/model');p=profile/'openclaw.json'
            cfg=read_json(p);cfg.pop('tools');p.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ContractError,'PROFILE_GLOBAL_READ_ONLY_TOOLS'):verify_profile(p,'legacy-list')
    def test_missing_global_denial_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile=stage(Path(tmp)/'profile','legacy-list','provider/model');p=profile/'openclaw.json'
            cfg=read_json(p);cfg['tools']['deny'].remove('sessions_history');p.write_text(json.dumps(cfg))
            with self.assertRaisesRegex(ContractError,'PROFILE_GLOBAL_TOOL_DENIALS'):verify_profile(p,'legacy-list')
    def test_writable_or_external_container_mount_fails_acceptance(self):
        item={'Name':'/test','HostConfig':{'NetworkMode':'none','ReadonlyRootfs':True,'Privileged':False,
            'CapDrop':['ALL'],'SecurityOpt':['no-new-privileges']},'Mounts':[{'Type':'bind','Source':'/outside','Destination':'/agent','RW':True}]}
        result=container_checks(item,'/private/teaching')
        self.assertFalse(result['all_container_checks_passed'])
        self.assertFalse(result['checks']['binds_read_only']);self.assertFalse(result['checks']['binds_inside_teaching_profile'])
    def test_cross_role_mount_fails_even_inside_same_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=Path(tmp).resolve()
            item={'Name':'/openclaw-sbx-agent-eg-student-feedback-check','HostConfig':{'NetworkMode':'none','ReadonlyRootfs':True,
                'Privileged':False,'CapDrop':['ALL'],'SecurityOpt':['no-new-privileges']},
                'Mounts':[{'Type':'bind','Source':str(state/'workspaces/eg-teacher-review'),'Destination':'/agent','RW':False}]}
            result=container_checks(item,state)
            self.assertTrue(result['checks']['binds_inside_teaching_profile'])
            self.assertFalse(result['checks']['agent_mount_matches_role'])
    def test_stale_preloaded_rules_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'TOOLS.md';p.write_text(bootstrap_context('eg-student-feedback')+'stale')
            with self.assertRaisesRegex(ContractError,'ROLE_CONTEXT_MISSING_OR_STALE'):verify_bootstrap('eg-student-feedback',tmp)
    def test_student_context_contains_required_references_without_teacher_role(self):
        resources=role_resources('eg-student-feedback','revision')
        self.assertTrue(any('revision-review' in r['name'] for r in resources))
        self.assertTrue(any('scoring-anchors' in r['name'] for r in resources))
        self.assertFalse(any('eg-rubric-check' in r['name'] for r in resources))


if __name__=='__main__':unittest.main()
