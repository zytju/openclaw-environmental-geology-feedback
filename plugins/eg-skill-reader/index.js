import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const roles = {
  'eg-student-feedback': ['eg-authenticity-anchor', 'eg-report-feedback'],
  'eg-teacher-review': ['eg-authenticity-anchor', 'eg-rubric-check'],
};
function regularRead(file, root, limit = 65536) {
  const real = fs.realpathSync(file);
  if (!real.startsWith(root + path.sep) || fs.lstatSync(file).isSymbolicLink()) throw Error('RESOURCE_OUTSIDE_ROLE');
  const fd = fs.openSync(file, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW);
  try {
    const stat = fs.fstatSync(fd);
    if (!stat.isFile() || stat.size > limit) throw Error('RESOURCE_SIZE_OR_TYPE');
    return fs.readFileSync(fd, 'utf8');
  } finally { fs.closeSync(fd); }
}
export function readRoleResource(ctx, args) {
  const allowed = roles[ctx.agentId];
  if (!allowed || !allowed.includes(args.skill)) throw Error('SKILL_NOT_ALLOWED_FOR_ROLE');
  if (!/^(SKILL\.md|references\/[A-Za-z0-9_.-]+\.(md|json|txt))$/.test(args.resource)) throw Error('RESOURCE_NAME_REJECTED');
  const cfg = ctx.getRuntimeConfig?.() ?? ctx.runtimeConfig ?? ctx.config;
  const agents = cfg?.agents?.list ?? Object.entries(cfg?.agents?.entries ?? {}).map(([id, v]) => ({id, ...v}));
  const agent = agents.find(a => a.id === ctx.agentId);
  if (!agent || !agent.workspace || !ctx.sessionId) throw Error('TRUSTED_CONTEXT_REQUIRED');
  const root = fs.realpathSync(agent.workspace);
  const manifest = JSON.parse(regularRead(path.join(root, 'skill-resources.json'), root));
  const key = `${args.skill}/${args.resource}`;
  if (manifest.agent_id !== ctx.agentId || !Object.hasOwn(manifest.files, key)) throw Error('RESOURCE_NOT_REGISTERED');
  const file = path.join(root, 'skills', key);
  const body = regularRead(file, root);
  const sha256 = crypto.createHash('sha256').update(body).digest('hex');
  if (sha256 !== manifest.files[key]) throw Error('RESOURCE_VERSION_MISMATCH');
  return {agent_id: ctx.agentId, session_id: ctx.sessionId, resource: key, sha256, body};
}
export default {
  id: 'eg-skill-reader',
  register(api) {
    api.registerTool(ctx => ({
      name: 'eg_skill_read',
      label: 'Read teaching Skill',
      description: 'Read a complete Skill instruction or reference for this teaching role. Call with the installed skill name and SKILL.md, or a linked references/file. No arbitrary files, commands or network.',
      parameters: {type: 'object', additionalProperties: false, required: ['skill', 'resource'], properties: {
        skill: {type: 'string', enum: ['eg-authenticity-anchor', 'eg-report-feedback', 'eg-rubric-check']},
        resource: {type: 'string', description: 'SKILL.md or references/name.md or references/name.json'}
      }},
      async execute(_id, args) {
        const value = readRoleResource(ctx, args);
        return {content: [{type: 'text', text: JSON.stringify(value)}], details: {resource: value.resource, sha256: value.sha256}};
      }
    }), {name: 'eg_skill_read', optional: true});
  }
};
