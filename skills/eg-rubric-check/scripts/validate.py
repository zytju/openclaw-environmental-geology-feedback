#!/usr/bin/env python3
"""Portable teacher-side checker; does not call an agent or external service."""
import argparse,json
from pathlib import Path
from contracts import *

p=argparse.ArgumentParser(description='教师侧校验。反馈与教师复核检查必须提供独立intake；已有gate文件不能替代教师材料审核。');p.add_argument('--submission',required=True);p.add_argument('--intake',help='一条符合teacher-intake.schema.json的教师核查记录，不是批处理数组');p.add_argument('--feedback');p.add_argument('--teacher-review')
a=p.parse_args();r=Path(__file__).resolve().parents[1]/'references'
try:
 s=read_json(a.submission);schemas={n:read_json(r/(n+'.schema.json')) for n in ['submission','teacher-intake','gate','feedback','teacher-review']}
 check_submission(s,schemas['submission'],read_json(r/'sources.json'))
 intake=read_json(a.intake) if a.intake else None
 if intake is not None:validate(intake,schemas['teacher-intake'])
 gate=material_gate(s,intake,read_json(r/'sources.json'));validate(gate,schemas['gate'])
 if a.feedback or a.teacher_review:require(intake is not None,'TEACHER_INTAKE_REQUIRED_FOR_FEEDBACK_CHECK')
 if a.feedback:
  f=read_json(a.feedback);check_feedback(f,s,gate,schemas['feedback'],read_json(r/'case-facts.json'))
 if a.teacher_review:
  require(bool(a.feedback),'FEEDBACK_REQUIRED_FOR_REVIEW')
  check_teacher(read_json(a.teacher_review),s,f,schemas['teacher-review'],read_json(r/'case-facts.json'))
 print(json.dumps(gate,ensure_ascii=False,indent=2))
 raise SystemExit(0 if gate['status']=='eligible' else 2)
except (ContractError,OSError,ValueError) as e:
 print(json.dumps({'status':'invalid','error':str(e)},ensure_ascii=False));raise SystemExit(1)
