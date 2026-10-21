"""Configure an opt-in role-scoped Skill reader in a private teaching profile."""
import hashlib
import json
from pathlib import Path
import shutil
from .contracts import require

ROOT=Path(__file__).resolve().parents[1]
READER='eg_skill_read'


def resource_manifest(agent,workspace):
    root=Path(workspace)/'skills';files={}
    for p in sorted(root.rglob('*')):
        if p.is_file() and (p.name=='SKILL.md' or (p.parent.name=='references' and p.suffix in ('.md','.json','.txt'))):
            require(not p.is_symlink() and p.resolve().is_relative_to(root.resolve()),'SKILL_RESOURCE_SYMLINK')
            files[p.relative_to(root).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
    return {'agent_id':agent,'files':files}


def verify_native_workspace(agent,workspace):
    p=Path(workspace)/'skill-resources.json'
    require(p.is_file() and json.loads(p.read_text())==resource_manifest(agent,workspace),'SKILL_RESOURCE_MANIFEST_STALE')
    professional='eg-report-feedback' if agent=='eg-student-feedback' else 'eg-rubric-check'
    for sk in ('eg-authenticity-anchor',professional):
        for f in (ROOT/'skills'/sk).rglob('*'):
            if f.is_file() and (f.name=='SKILL.md' or f.parent.name=='references'):
                other=Path(workspace)/'skills'/sk/f.relative_to(ROOT/'skills'/sk)
                require(other.is_file() and other.read_bytes()==f.read_bytes(),'SKILL_RESOURCE_SOURCE_STALE')
    return True


def configure_on_demand(config):
    from .pipeline import verify_profile
    p=Path(config).resolve(strict=True);cfg=json.loads(p.read_text())
    layout='legacy-list' if 'list' in cfg['agents'] else 'current-entries'
    verify_profile(p,layout)
    plugin=p.parent/'plugins/eg-skill-reader'
    require(not plugin.exists(),'SKILL_READER_ALREADY_CONFIGURED')
    shutil.copytree(ROOT/'plugins/eg-skill-reader',plugin)
    cfg.setdefault('plugins',{}).setdefault('allow',[]).append('eg-skill-reader')
    cfg['plugins'].setdefault('load',{}).setdefault('paths',[]).append(str(plugin))
    cfg['plugins'].setdefault('entries',{})['eg-skill-reader']={'enabled':True}
    cfg['plugins']['entries'].setdefault('codex',{}).setdefault('config',{})['codexDynamicToolsLoading']='direct'
    entries=cfg['agents'].get('list') or [dict(id=k,**v) for k,v in cfg['agents']['entries'].items()]
    for tools in [cfg['tools']]+[a['tools'] for a in entries]:
        tools['allow']=[READER]
        tools['sandbox']={'tools':{'allow':[READER],'deny':tools['deny'][:]}}
        tools['fs']={'workspaceOnly':True}
    for a in entries:
        ws=Path(a['workspace']);(ws/'skill-resources.json').write_text(json.dumps(resource_manifest(a['id'],ws),ensure_ascii=False,indent=2)+'\n')
        (ws/'TOOLS.md').write_text('# 按需读取教学规则\n每个任务先用eg_skill_read读取本角色Skill的SKILL.md，再按任务读取链接的参考文件。只接收技能名和相对资源名，不读取其他目录。本文件不包含Skill正文。\n')
    backup=p.with_name('openclaw.before-skill-reader.json');require(not backup.exists(),'CONFIG_BACKUP_EXISTS');shutil.copy2(p,backup)
    p.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
    return p
