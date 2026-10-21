import copy,json
from pathlib import Path
import tempfile,unittest
from egtool.contracts import ContractError,check_feedback,material_gate,read_json
from egtool.explicit_links import normalize_explicit_links
from egtool.pipeline import MockBackend,mock_submission,mock_intake,assets
from egtool.synthetic_live import read_values

class RelatedTaskTests(unittest.TestCase):
 def setUp(self):
  self.sub=mock_submission();self.it=mock_intake(self.sub);self.fb=MockBackend().generate('student',self.sub)
  self.schemas,self.sources,self.facts=assets();d=self.fb['dimensions'][4];d.update(assessment='partial',level_proposal=1,issues=[],basis='核心断言仍需修订，相关任务已列在推理链问题I03中。')
 def check(self,fb):return check_feedback(fb,self.sub,material_gate(self.sub,self.it,self.sources),self.schemas['feedback'],self.facts)
 def test_explicit_relation_preserves_every_original_field(self):
  fb,record=normalize_explicit_links(self.fb);self.check(fb);self.assertEqual(fb['dimensions'][4]['related_issue_ids'],['I03'])
  reduced=copy.deepcopy(fb);reduced['dimensions'][4].pop('related_issue_ids');self.assertEqual(reduced,self.fb)
  self.assertFalse(record['assessment_and_text_changed']);self.assertFalse(record['teacher_approval_created'])
 def test_missing_task_id_is_not_invented(self):
  self.fb['dimensions'][4]['basis']='本维尚有重要问题，应继续修改。';fb,rec=normalize_explicit_links(self.fb)
  self.assertFalse(rec['changes'])
  with self.assertRaisesRegex(ContractError,'ISSUE_REQUIRED_FOR_GAP'):self.check(fb)
 def test_dangling_reference_is_rejected(self):
  self.fb['dimensions'][4]['related_issue_ids']=['I99']
  with self.assertRaisesRegex(ContractError,'RELATED_ISSUE_UNKNOWN'):self.check(self.fb)
 def test_out_of_scope_cannot_link_to_student_tasks(self):
  self.sub.update(report_scope='excerpt',assessed_dimensions=['reasoning_chain']);self.it=mock_intake(self.sub)
  fb=MockBackend().generate('student',self.sub);fb['dimensions'][4]['related_issue_ids']=['I03']
  with self.assertRaisesRegex(ContractError,'OUT_OF_SCOPE_NO_ISSUES'):self.check(fb)
 def test_nested_tool_returns_are_read_as_complete_resources(self):
  value={'agent_id':'eg-student-feedback','session_id':'test','resource':'eg-report-feedback/SKILL.md','sha256':'x','body':'all rules'}
  for raw in [json.dumps(value),json.dumps({'a':json.dumps(value)}),json.dumps([json.dumps(value)])]:self.assertEqual(list(read_values(raw)),[value])

if __name__=='__main__':unittest.main()
