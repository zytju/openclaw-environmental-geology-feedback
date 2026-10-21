#!/usr/bin/env python3
"""Collect local config and container evidence without calling a model."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from egtool.runtime_audit import audit_runtime
p=argparse.ArgumentParser(description='只读核验独立教学运行配置，不自动批准生产运行。')
for key in ['executable','config','layout','out']:p.add_argument('--'+key,required=True)
p.add_argument('--docker',help='可选Docker可执行文件；仅检查本profile的活动教学容器')
a=p.parse_args();r=audit_runtime(a.executable,a.config,a.layout,a.out,a.docker)
print(json.dumps({'native_config_valid':r['native_config_valid'],'active_containers':len(r['active_containers']),
 'production_isolation_verified':r['production_isolation_verified'],'evidence_file':a.out},ensure_ascii=False))
