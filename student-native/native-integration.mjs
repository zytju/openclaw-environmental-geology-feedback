// Actual OpenClaw + local compatible API fixture. No real model or real key.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import http from 'node:http';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import { install, selfcheck, feedback, DIMS } from './course.mjs';
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'eg-real-openclaw-'));
const root = path.join(temp, 'course'), dummy = 'local-fixture-' + crypto.randomBytes(20).toString('hex'), seen = [];
const server = http.createServer(async (req, res) => {
  let text = ''; for await (const b of req) text += b;
  const body = JSON.parse(text); seen.push(body);
  assert.equal(req.headers.authorization, 'Bearer ' + dummy);
  assert.ok(!body.tools || body.tools.length === 0, 'model must receive zero tools');
  const prompt = body.messages.filter(x => x.role === 'user').at(-1).content;
  const s = typeof prompt === 'string' ? prompt : prompt.map(x => x.text || '').join('\n');
  const request = JSON.parse(s.slice(s.indexOf('{"policy":'), s.lastIndexOf('}') + 1)), r = request.report;
  const content = JSON.stringify({ summary: '这是本机兼容接口合成测试，不是真实模型专业反馈。',
    dimensions: DIMS.map(d => ({ dimension: d, status: 'partial', paragraph_id: 'P001', quote: r.report_text.split('\n')[0],
      observation: '合成响应仅检查原生传输和反馈协议。', action: '实际专业反馈必须接通真实模型后另行验证。' })), priorities: DIMS.slice(0, 2) });
  if (body.stream) {
    res.writeHead(200, { 'Content-Type': 'text/event-stream' });
    res.write('data: ' + JSON.stringify({ id: 'fixture', object: 'chat.completion.chunk', created: 1, model: body.model,
      choices: [{ index: 0, delta: { role: 'assistant', content }, finish_reason: null }] }) + '\n\n');
    res.write('data: ' + JSON.stringify({ id: 'fixture', object: 'chat.completion.chunk', created: 1, model: body.model,
      choices: [{ index: 0, delta: {}, finish_reason: 'stop' }], usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 } }) + '\n\n');
    res.end('data: [DONE]\n\n');
  } else {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ id: 'fixture', object: 'chat.completion', model: body.model, choices: [{ index: 0, message: { role: 'assistant', content }, finish_reason: 'stop' }] }));
  }
});
await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
try {
  install({ root });
  const configPath = path.join(root, 'openclaw.json'), c = JSON.parse(fs.readFileSync(configPath));
  c.models.providers['eg-deepseek'].baseUrl = 'http://127.0.0.1:' + server.address().port;
  fs.writeFileSync(configPath, JSON.stringify(c));
  const metaPath = path.join(root, 'course-install.json'), m = JSON.parse(fs.readFileSync(metaPath));
  m.backend = 'local-compatible-api-fixture';m.files['openclaw.json'] = crypto.createHash('sha256').update(fs.readFileSync(configPath)).digest('hex');
  fs.writeFileSync(metaPath, JSON.stringify(m));
  const check = await selfcheck(root);
  const a = await feedback(root, { report_title: '三峡库区滑坡测试甲', report_text: '三峡库区滑坡测试甲的独立正文。' }, { key: dummy });
  const b = await feedback(root, { report_title: '三峡库区滑坡测试乙', report_text: '三峡库区滑坡测试乙的独立正文。' }, { key: dummy });
  assert.notEqual(a.session, b.session);assert.equal(a.feedback.dimensions.length, 6);
  assert.deepEqual(a.gate.optional_missing, ['raw_analysis', 'evidence_cards']);assert.equal(seen.length, 2);
  assert.ok(!JSON.stringify(seen[1]).includes('测试甲的独立正文'), 'second request must not inherit first report');
  for (const body of seen) {
    const prompt = JSON.stringify(body.messages);
    assert.ok(prompt.includes('eg-authenticity-anchor') && prompt.includes('eg-report-feedback') && prompt.includes('midterm-literature-2026'));
  }
  function scan(dir) {
    for (const f of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, f.name);
      if (f.isDirectory()) scan(p);
      else if (f.isFile()) assert.ok(!fs.readFileSync(p).includes(Buffer.from(dummy)), 'dummy key persisted: ' + f.name);
    }
  }
  scan(root);
  console.log(JSON.stringify({ test: 'real OpenClaw with local compatible API fixture', modelCalled: false, selfcheck: check,
    requests: seen.length, sixDimensions: true, optionalMaterialsAbsent: true, zeroTools: true,
    distinctSessions: true, crossSessionInputAbsent: true, dummyKeyNotPersisted: true }, null, 2));
} finally {
  await new Promise(resolve => server.close(resolve));fs.rmSync(temp, { recursive: true, force: true });
}
