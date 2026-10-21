import assert from 'node:assert/strict';
import fs from 'node:fs';import os from 'node:os';import path from 'node:path';import crypto from 'node:crypto';
import {readRoleResource} from './index.js';
const root=fs.mkdtempSync(path.join(os.tmpdir(),'eg-skill-test-'));
try {
 const dir=path.join(root,'skills/eg-report-feedback');fs.mkdirSync(dir,{recursive:true});fs.writeFileSync(path.join(dir,'SKILL.md'),'test skill instructions');
 const sha=crypto.createHash('sha256').update('test skill instructions').digest('hex');
 fs.writeFileSync(path.join(root,'skill-resources.json'),JSON.stringify({agent_id:'eg-student-feedback',files:{'eg-report-feedback/SKILL.md':sha}}));
 const ctx={agentId:'eg-student-feedback',sessionId:'test-session',config:{agents:{list:[{id:'eg-student-feedback',workspace:root}]}}};
 assert.equal(readRoleResource(ctx,{skill:'eg-report-feedback',resource:'SKILL.md'}).body,'test skill instructions');
 assert.throws(()=>readRoleResource(ctx,{skill:'eg-rubric-check',resource:'SKILL.md'}),/SKILL_NOT_ALLOWED/);
 assert.throws(()=>readRoleResource(ctx,{skill:'eg-report-feedback',resource:'../../openclaw.json'}),/RESOURCE_NAME/);
 assert.throws(()=>readRoleResource(ctx,{skill:'eg-report-feedback',resource:'references/not-installed.json'}),/NOT_REGISTERED/);
 assert.throws(()=>readRoleResource({...ctx,sessionId:undefined},{skill:'eg-report-feedback',resource:'SKILL.md'}),/TRUSTED_CONTEXT/);
 fs.writeFileSync(path.join(dir,'SKILL.md'),'changed version');assert.throws(()=>readRoleResource(ctx,{skill:'eg-report-feedback',resource:'SKILL.md'}),/VERSION_MISMATCH/);
 fs.unlinkSync(path.join(dir,'SKILL.md'));fs.symlinkSync('/etc/hosts',path.join(dir,'SKILL.md'));assert.throws(()=>readRoleResource(ctx,{skill:'eg-report-feedback',resource:'SKILL.md'}),/OUTSIDE_ROLE/);
 console.log('Skill reader: 7 behavioral checks passed.');
} finally {fs.rmSync(root,{recursive:true,force:true});}
