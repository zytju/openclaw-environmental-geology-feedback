"""Live serial testing confined to synthetic submissions, without production approval."""
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
from .pipeline import OpenClawBackend,verify_profile,assets,save,save_text,unwrap_openclaw,numeric_cli_metrics
from .contracts import require,digest,check_submission,check_feedback,check_teacher,material_gate,read_json


def read_values(value,depth=0):
    if depth>8:return
    if isinstance(value,str):
        if not value.startswith(('{','[')):return
        try:value=json.loads(value)
        except ValueError:return
        yield from read_values(value,depth+1)
    elif isinstance(value,list):
        for v in value:yield from read_values(v,depth+1)
    elif isinstance(value,dict):
        if {'agent_id','session_id','resource','sha256','body'}<=value.keys():yield value
        else:
            for v in value.values():yield from read_values(v,depth+1)


class SyntheticLiveBackend(OpenClawBackend):
    def __init__(self,executable,config,audit,confirmed=False,resume=False):
        require(confirmed,'SYNTHETIC_LIVE_CONFIRMATION_REQUIRED')
        self.executable=str(Path(executable).resolve(strict=True));self.config=Path(config).resolve(strict=True)
        cfg=verify_profile(self.config,'legacy-list')
        require(cfg['tools']['allow']==['eg_skill_read'],'ON_DEMAND_READER_REQUIRED')
        self.native_reader=True;self.env=os.environ.copy()
        self.env.update(OPENCLAW_CONFIG_PATH=str(self.config),OPENCLAW_STATE_DIR=str(self.config.parent))
        self.audit=Path(audit);self.audit.mkdir(parents=True,exist_ok=resume,mode=0o700)
        self.timeout=360;self.call_count=max([int(p.name.split('-')[0]) for p in self.audit.glob('*.cli.private.json')],default=0);self.last_evidence=None;self.last_call_metrics={}

    def generate(self,role,sub,feedback=None,session_id=None):
        require(sub['material_kind']=='synthetic','SYNTHETIC_LIVE_REAL_WORK_FORBIDDEN')
        self.call_count+=1;require(self.call_count<=132,'SYNTHETIC_CALL_LIMIT')
        self.current_prefix=f'{self.call_count:03d}-{sub["student_id"]}-{role}'
        value=super().generate(role,sub,feedback,session_id)
        if role=='student':
            from .explicit_links import normalize_explicit_links
            value,record=normalize_explicit_links(value)
            save(self.audit/(self.current_prefix+'.normalization.json'),record)
        return value

    def retain_result(self,text,started):
        raw=self.audit/(self.current_prefix+'.cli.private.json')
        if raw.exists():require(raw.read_text()==text,'CACHED_MODEL_RESPONSE_CHANGED')
        else:save_text(raw,text)
        body=json.loads(text);body=body.get('result',body);meta=body['meta'];am=meta['agentMeta']
        require(meta.get('aborted') is False,'LIVE_TURN_ABORTED')
        require(am.get('provider')=='openai' and am.get('model')=='gpt-5.6-sol','LIVE_MODEL_CHANGED')
        sid=am['sessionId'];agent='eg-student-feedback' if self.current_prefix.endswith('student') else 'eg-teacher-review'
        resources=[]
        for p in (self.config.parent/'agent-state'/agent/'codex-home/sessions').rglob('rollout-*.jsonl'):
            if p.stat().st_mtime<started-2:continue
            for line in p.read_text().splitlines():
                event=json.loads(line);payload=event.get('payload',{})
                if payload.get('type') not in ('custom_tool_call_output','function_call_output'):continue
                output=payload.get('output',[])
                if not isinstance(output,list):continue
                for item in output:
                    text=item.get('text','') if isinstance(item,dict) else ''
                    for value in read_values(text):
                        if value.get('session_id')!=sid or value.get('agent_id')!=agent:continue
                        import hashlib
                        require(hashlib.sha256(value['body'].encode()).hexdigest()==value['sha256'],'READ_EVIDENCE_BODY_HASH')
                        resources.append({k:value[k] for k in ('resource','sha256')})
        professional='eg-report-feedback' if agent=='eg-student-feedback' else 'eg-rubric-check'
        names={x['resource'] for x in resources}
        require({professional+'/SKILL.md','eg-authenticity-anchor/SKILL.md'}<=names,'ACTUAL_SKILL_READ_NOT_OBSERVED')
        self.last_evidence={'session_id':sid,'agent_id':agent,'provider':am['provider'],'model':am['model'],
            'resources':resources,'usage':am.get('usage'),'duration_ms':meta.get('durationMs')}
        evidence=self.audit/(self.current_prefix+'.read-evidence.json')
        if evidence.exists():require(read_json(evidence)==self.last_evidence,'CACHED_READ_EVIDENCE_CHANGED')
        else:save(evidence,self.last_evidence)


def serial_test(inputs,intakes,out,backend,count=66,resume=False):
    require(1<=count<=66,'SYNTHETIC_TEST_COUNT')
    schemas,sources,facts=assets();files=sorted(Path(inputs).glob('*.json'));require(len(files)>=count,'SYNTHETIC_INPUT_COUNT')
    intakes=read_json(intakes);reviewmap={i['student_id']:i for i in intakes}
    prepared=[]
    for p in files[:count]:
        s=read_json(p);check_submission(s,schemas['submission'],sources);require(s['material_kind']=='synthetic','SYNTHETIC_INPUT_ONLY')
        i=reviewmap[s['student_id']];g=material_gate(s,i,sources);require(g['status']=='eligible','SYNTHETIC_GATE_CLOSED');prepared.append((s,i,g))
    out=Path(out);require(not out.exists() or resume,'OUTPUT_EXISTS');out.mkdir(parents=True,exist_ok=resume,mode=0o700)
    prior=read_json(out/'progress.private.json') if resume and (out/'progress.private.json').exists() else {}
    prior_rows={r['student_id']:r for r in prior.get('records',[])}
    summary={'kind':'synthetic_real_model_serial_test','planned_submissions':count,'completed_submissions':0,
        'successful_model_calls':0,'human_final_reviews':0,'confirmed_beneficiaries':None,'production_isolation_verified':False,
        'records':[],'status':'running','started_at':time.time()}
    for sub,intake,gate in prepared:
        sid=sub['student_id'];folder=out/sid
        if folder.exists():
            require(resume and read_json(folder/'submission.json')==sub and read_json(folder/'intake.json')==intake,'RESUME_INPUT_CHANGED')
        else:
            folder.mkdir();save(folder/'submission.json',sub);save(folder/'intake.json',intake)
        backend.intake=intake;row={'student_id':sid,'calls':[],'status':'running'};summary['records'].append(row)
        try:
            for role in ('student','teacher'):
                cached=folder/('feedback.json' if role=='student' else 'teacher-review.json')
                started=time.time();fb=read_json(folder/'feedback.json') if role=='teacher' else None
                reused=resume and cached.exists()
                if reused:
                    value=read_json(cached);matches=list(backend.audit.glob('*-'+sid+'-'+role+'.cli.private.json'))
                    require(len(matches)==1,'RESUME_RESPONSE_AMBIGUOUS')
                    backend.last_call_metrics=numeric_cli_metrics(matches[0].read_text())
                    evidence=matches[0].with_name(matches[0].name.replace('.cli.private.json','.read-evidence.json'))
                    require(evidence.is_file(),'RESUME_READ_EVIDENCE_MISSING');backend.last_evidence=read_json(evidence)
                else:value=backend.generate(role,sub,fb,str(uuid.uuid4()))
                if role=='student':check_feedback(value,sub,gate,schemas['feedback'],facts)
                else:check_teacher(value,sub,fb,schemas['teacher-review'],facts)
                if not cached.exists():save(cached,value)
                old=next((x for x in prior_rows.get(sid,{}).get('calls',[]) if x['role']==role),None) if reused else None
                row['calls'].append(dict(old,reused_completed_response=True) if old else {'role':role,'seconds':None if reused else round(time.time()-started,3),'reused_completed_response':reused,'metrics':backend.last_call_metrics,
                                     'skill_read_evidence':backend.last_evidence})
                summary['successful_model_calls']+=1
                print(json.dumps({'student_id':sid,'role':role,'completed_calls':summary['successful_model_calls'],'seconds':row['calls'][-1]['seconds']},ensure_ascii=False),flush=True)
            row['status']='protocol_valid';summary['completed_submissions']+=1
        except Exception as e:
            row.update(status='stopped_on_error',error=str(e));summary['status']='stopped_on_error';summary['error']=str(e)
        (out/'progress.private.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
        if summary['status']!='running':break
    if summary['status']=='running':summary['status']='complete'
    summary['elapsed_seconds']=round(time.time()-summary['started_at'],3)
    summary['reported_call_seconds_total']=round(sum((c['metrics'].get('reported_duration_ms') or 0)/1000 for r in summary['records'] for c in r['calls']),3)
    final=out/(f'result-resumed-{count}.json' if resume else 'result.json');save(final,summary)
    return summary
