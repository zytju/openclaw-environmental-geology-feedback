"""Read-only runtime evidence. Config declarations are not isolation acceptance."""
import os
from pathlib import Path
import subprocess
from .contracts import require,loads,digest,read_json
from .pipeline import verify_profile,save,stamp


def container_checks(item,state):
    host=item['HostConfig'];mounts=item.get('Mounts',[])
    state=Path(state).resolve()
    sources=[Path(m['Source']).resolve() for m in mounts if m.get('Type')=='bind']
    agent_sources=[Path(m['Source']).resolve() for m in mounts if m.get('Type')=='bind' and m.get('Destination')=='/agent']
    name=item.get('Name','')
    role=next((r for r in ['eg-student-feedback','eg-teacher-review'] if r in name),None)
    checks={'network_none':host.get('NetworkMode')=='none','root_read_only':host.get('ReadonlyRootfs') is True,
        'not_privileged':host.get('Privileged') is False,'all_capabilities_dropped':'ALL' in (host.get('CapDrop') or []),
        'no_new_privileges':'no-new-privileges' in (host.get('SecurityOpt') or []),
        'binds_read_only':bool(sources) and all(not m.get('RW') for m in mounts if m.get('Type')=='bind'),
        'binds_inside_teaching_profile':bool(sources) and all(p.is_relative_to(state) for p in sources),
        'agent_mount_matches_role':role is not None and agent_sources==[(state/'workspaces'/role).resolve()]}
    role_mounts=[m['Destination'] for m in mounts if m.get('Type')=='bind']
    return {'name':item.get('Name','').lstrip('/'),'checks':checks,'all_container_checks_passed':all(checks.values()),
        'bind_destinations':role_mounts}


def audit_runtime(executable,config,layout,out,docker=None):
    config=Path(config).resolve(strict=True);cfg=verify_profile(config,layout)
    env=os.environ.copy();env.pop('OPENCLAW_PROFILE',None)
    env.update(OPENCLAW_CONFIG_PATH=str(config),OPENCLAW_STATE_DIR=str(config.parent))
    def call(args,timeout=30):
        r=subprocess.run(args,env=env,capture_output=True,text=True,timeout=timeout)
        require(r.returncode==0,'RUNTIME_COMMAND_FAILED_'+args[1].upper())
        return r.stdout
    version=call([executable,'--version']).strip()
    native=loads(call([executable,'config','validate','--json']))
    require(native.get('valid') is True,'NATIVE_CONFIG_REJECTED')
    roles=[]
    for role in ['eg-student-feedback','eg-teacher-review']:
        value=loads(call([executable,'sandbox','explain','--agent',role,'--json']))
        sandbox=value.get('sandbox',{})
        roles.append({'agent':role,'effective_mode':sandbox.get('mode'),'effective_scope':sandbox.get('scope'),
            'workspace_access':sandbox.get('workspaceAccess'),
            'policy_evidence_sha256':digest(value)})
    containers=[]
    if docker:
        ids=call([docker,'ps','-q','--filter','name=openclaw-sbx-agent-eg-']).split()
        if ids:
            for item in loads(call([docker,'inspect',*ids])):
                sources=[Path(m['Source']).resolve() for m in item.get('Mounts',[]) if m.get('Type')=='bind']
                if sources and all(p.is_relative_to(config.parent) for p in sources):containers.append(container_checks(item,config.parent))
    report={'timestamp':stamp(),'runtime_version':version,'config_sha256':digest(cfg),'native_config_valid':True,
        'global_and_agent_policies_valid':True,'roles':roles,'active_containers':containers,
        'native_skill_file_reads_verified':False,'native_tool_boundaries_verified':False,
        'cross_session_read_probe_verified':False,'production_isolation_verified':False,
        'note':'配置与容器证据分别保存。原生文件读取、原生工具边界和跨会话实测须另附实际探针结果；不自动签认部署审批。'}
    save(out,report);return report
