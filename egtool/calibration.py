"""Blind calibration packets and explicit result checks, separate from grading."""
import copy
from .contracts import require, validate


RESULT_SCHEMA={'type':'object','additionalProperties':False,'required':['results'],'properties':{
 'results':{'type':'array','items':{'type':'object','additionalProperties':False,
 'required':['case_id','decision','level','reason'],'properties':{
 'case_id':{'type':'string'},'decision':{'type':'string','enum':['needs_revision','no_basis_for_criticism',
 'evidence_status_error','supported_partial_adoption','level_two','not_in_scope','hold_for_teacher']},
 'level':{'type':['integer','null'],'minimum':0,'maximum':3},'reason':{'type':'string','minLength':8}}}}}}


def blind_packet(suite):
    require(suite.get('material_kind')=='synthetic','CALIBRATION_SYNTHETIC_REQUIRED')
    cases=copy.deepcopy(suite['cases'])
    require(len({x['case_id'] for x in cases})==len(cases),'CALIBRATION_DUPLICATE_CASE')
    for case in cases:case.pop('expected')
    return {'task':'规则校准测试，不是学生作业或教师终审。逐案回答指定问题，给出原文依据。level仅在问题要求时给出，否则为null。',
            'material_kind':'synthetic','cases':cases,'output_schema':copy.deepcopy(RESULT_SCHEMA)}


def evaluate(suite,result):
    validate(result,RESULT_SCHEMA)
    expected={x['case_id']:x['expected'] for x in suite['cases']}
    rows=result['results'];ids=[x['case_id'] for x in rows]
    require(len(ids)==len(set(ids)),'CALIBRATION_DUPLICATE_RESULT')
    require(set(ids)==set(expected),'CALIBRATION_CASE_SET_MISMATCH')
    checks=[]
    for row in rows:
        target=expected[row['case_id']]
        checks.append({'case_id':row['case_id'],'passed':all(row[k]==v for k,v in target.items()),
                       'expected':target,'actual':{k:row[k] for k in target}})
    return {'material_kind':'synthetic','cases':len(checks),'passed':sum(x['passed'] for x in checks),
            'all_passed':all(x['passed'] for x in checks),'checks':checks,
            'scope':'仅比较校准案例的决策与等级；理由仍需人工核查，不证明其他报告判断可靠。'}
