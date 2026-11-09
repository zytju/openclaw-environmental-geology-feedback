import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { install, verifyProfile, gate, checkFeedback, DIMS, selfcheck, feedback, invoke, serve, HERE } from './course.mjs';
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'eg-native-tests-'));
const root = path.join(temp, 'course');
install({ root });
const report = { report_title: '三峡库区滑坡灾害链', report_text: '三峡库区滑坡的孔隙水压力与库水变化有关。\n由滑坡入水推演后续涌浪风险，但需要核对地形及体积证据。' };
const value = r => ({ summary: '这是离线合成数据，只验证课程输出协议，不是专业模型反馈。',
  dimensions: DIMS.map(d => ({ dimension: d, status: 'partial', paragraph_id: 'P001',
    quote: r.report_text.split('\n')[0], observation: '合成检查：此处仅验证结构和引文归属。',
    action: '合成检查：真实建议必须由经验证的模型提供。' })), priorities: DIMS.slice(0, 2) });
const fixture = path.join(temp, 'fake-openclaw.mjs');
fs.writeFileSync(fixture, [
  "import fs from 'node:fs';",
  'const a=process.argv.slice(2);',
  "if(a[0]==='--version') console.log('OpenClaw 2026.7.1-2 (offline fixture)');",
  "else if(a[0]==='config') console.log(JSON.stringify({valid:true}));",
  "else if(a[0]==='agents') console.log(JSON.stringify([{id:'eg-student-feedback'}]));",
  "else if(a[0]==='skills') console.log(JSON.stringify({skills:[{name:'eg-authenticity-anchor',eligible:true},{name:'eg-report-feedback',eligible:true}]}));",
  "else if(a[0]==='agent'){",
  "const s=fs.readFileSync(a[a.indexOf('--message-file')+1],'utf8');let text='课程连接测试成功';",
  "if(s.startsWith('{')){const q=JSON.parse(s);text=JSON.stringify((" + value.toString() + ")(q.report));}",
  "console.log(JSON.stringify({payloads:[{text}],meta:{fixture:true,agentMeta:{sessionId:a[a.indexOf('--session-id')+1]},systemPromptReport:{tools:{entries:[]},skills:{entries:[{name:'eg-authenticity-anchor'},{name:'eg-report-feedback'}]},injectedWorkspaceFiles:[{name:'TOOLS.md',truncated:false}]}}}));",
  "} else process.exitCode=1;"
].join('\n').replaceAll('DIMS', JSON.stringify(DIMS)));
test.after(() => fs.rmSync(temp, { recursive: true, force: true }));
test('both optional materials absent still eligible and six dimensions valid', () => {
  assert.deepEqual(gate(report).optional_missing, ['raw_analysis', 'evidence_cards']);
  assert.equal(gate(report).status, 'eligible'); assert.equal(checkFeedback(value(report), report).dimensions.length, 6);
});
test('all four optional-material combinations are nonblocking', () => {
  for (const a of ['', '阅读草图']) for (const b of ['', '来源及摘录']) assert.equal(gate({ ...report, raw_analysis: a, evidence_cards: b }).status, 'eligible');
});
test('short body and missing references only warn', () => { const g = gate(report); assert.ok(g.warnings.length >= 3); assert.equal(g.status, 'eligible'); });
test('PII and off-topic input rejected', () => {
  assert.throws(() => gate({ ...report, report_text: report.report_text + '\n学号：12345' }));
  assert.throws(() => gate({ report_title: '城市污染', report_text: '地下水' }));
});
test('cannot smuggle role, path, session, or config fields into submission', () => {
  for (const key of ['agent', 'session', 'path', 'policy', 'config']) assert.throws(() => gate({ ...report, [key]: 'eg-teacher-review' }));
});
test('invented quotes and wrong dimensions rejected', () => {
  const v = value(report);v.dimensions[0].quote = '并不存在的原文';assert.throws(() => checkFeedback(v, report));
  const w = value(report);w.dimensions.reverse();assert.throws(() => checkFeedback(w, report));
});
test('absence uses REPORT/null, never fabricated quotation', () => {
  const v=value(report);Object.assign(v.dimensions[0],{status:'absent',paragraph_id:'REPORT',quote:null});checkFeedback(v,report);
  v.dimensions[0].quote='原文';assert.throws(()=>checkFeedback(v,report));
});
test('install contains only student and two skills; secret is an env reference', () => {
  const {config:c}=verifyProfile(root);assert.equal(c.agents.list.length,1);assert.deepEqual(c.tools.deny,['*']);
  assert.deepEqual(c.agents.list[0].tools.deny,['*']);assert.equal(c.plugins.enabled,false);
  assert.ok(c.models.providers['eg-deepseek'].apiKey.startsWith('$'));
  assert.deepEqual(fs.readdirSync(path.join(root,'workspace/skills')).sort(),['eg-authenticity-anchor','eg-report-feedback']);
  assert.equal(fs.existsSync(path.join(root,'workspace/skills/eg-rubric-check')),false);
});
test('existing personal directory is never overwritten; repeat install is idempotent', () => {
  assert.equal(install({root}).existing,true);const p=path.join(temp,'personal');fs.mkdirSync(p);fs.writeFileSync(path.join(p,'keep.txt'),'keep');
  assert.throws(()=>install({root:p}));assert.equal(fs.readFileSync(path.join(p,'keep.txt'),'utf8'),'keep');
});
test('tampered configuration stops before model invocation', () => {
  const p=path.join(temp,'tamper');install({root:p});fs.appendFileSync(path.join(p,'openclaw.json'),' ');assert.throws(()=>verifyProfile(p));
});
test('native CLI fixture validates JSON array agent list', async () => { const r=await selfcheck(root,{entry:fixture});assert.equal(r.modelCalled,false);assert.equal(r.ok,true); });
test('native launcher enforces six dimensions and distinct per-run sessions', async () => {
  const a=await feedback(root,report,{entry:fixture,key:'fixture-not-a-real-key'}),b=await feedback(root,{...report,report_title:'三峡库区滑坡第二份'},{entry:fixture,key:'fixture-not-a-real-key'});
  assert.notEqual(a.session,b.session);assert.equal(a.feedback.dimensions.length,6);
  assert.equal(fs.existsSync(path.join(root,'runs',a.session,'request.txt')),false);
});
test('missing runtime audit is rejected instead of claiming zero tools', async () => {
  const bad=path.join(temp,'missing-audit.mjs');
  fs.writeFileSync(bad,fs.readFileSync(fixture,'utf8').replace('meta:{fixture:true,agentMeta:', 'meta:{fixture:true,ignored:'));
  await assert.rejects(feedback(root,report,{entry:bad,key:'fixture-not-a-real-key'}),/运行记录/);
});
test('timeout ends native process and its child instead of leaving background work', async () => {
  const slow=path.join(temp,'slow-native.mjs'),started=path.join(temp,'started.txt'),late=path.join(temp,'late.txt');
  const childCode="setTimeout(()=>require('node:fs').writeFileSync("+JSON.stringify(late)+",'unexpected'),2000)";
  fs.writeFileSync(slow,"import fs from 'node:fs';import {spawn} from 'node:child_process';fs.writeFileSync("+JSON.stringify(started)+",'started');spawn(process.execPath,['-e',"+JSON.stringify(childCode)+"],{stdio:'ignore'});setTimeout(()=>{},60000);");
  await assert.rejects(invoke(root,'offline timeout test',{entry:slow,key:'fixture-not-a-real-key',timeoutMs:1000}),/超时/);
  assert.equal(fs.existsSync(started),true);
  await new Promise(resolve=>setTimeout(resolve,2500));
  assert.equal(fs.existsSync(late),false);
});
test('66 offline native CLI fixtures keep distinct sessions and report titles', async () => {
  const results=[];for(let start=0;start<66;start+=6) results.push(...await Promise.all(Array.from({length:Math.min(6,66-start)},(_,i)=>feedback(root,{...report,report_title:'三峡库区滑坡离线测试'+(start+i)},{entry:fixture,key:'fixture-not-a-real-key'}))));
  assert.equal(new Set(results.map(x=>x.session)).size,66);assert.equal(new Set(results.map(x=>x.title)).size,66);
  for(const r of results)assert.equal(r.feedback.dimensions.length,6);
});
test('loopback service requires fresh token; blocks cross-origin and management routes', async () => {
  const a=await serve(root),b=await serve(root);const origin=new URL(a.url).origin,token=new URL(a.url).hash.slice(1);
  try {
    assert.equal((await fetch(origin+'/api/status')).status,403);
    assert.equal((await fetch(origin+'/api/status',{headers:{'X-Course-Token':new URL(b.url).hash.slice(1)}})).status,403);
    assert.equal((await fetch(origin+'/api/status',{headers:{'X-Course-Token':token,Origin:'https://evil.example'}})).status,403);
    assert.equal((await fetch(origin+'/api/status',{headers:{'X-Course-Token':token}})).status,200);
    for(const route of ['/api/exec','/api/files','/api/config','/api/teacher','/api/sessions'])assert.equal((await fetch(origin+route,{method:'POST',headers:{'X-Course-Token':token},body:'{}'})).status,404);
    assert.equal((await fetch(origin+'/api/feedback',{method:'POST',headers:{'X-Course-Token':token},body:JSON.stringify(report)})).status,400);
  } finally {await Promise.all([new Promise(r=>a.server.close(r)),new Promise(r=>b.server.close(r))]);}
});
test('student page renders model text as text and screenshot remains optional', () => {
  const page=fs.readFileSync(path.join(HERE,'web.html'),'utf8');assert.ok(page.includes('textContent'));assert.ok(!page.includes('innerHTML'));assert.ok(page.includes('截图选交'));assert.ok(page.includes('至少2篇研究性论文'));
});
