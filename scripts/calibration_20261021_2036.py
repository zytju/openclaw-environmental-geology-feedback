#!/usr/bin/env python3
"""Prepare a blind packet or check independently supplied calibration results."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from egtool.calibration import blind_packet,evaluate
from egtool.contracts import read_json
from egtool.pipeline import ROOT,save

p=argparse.ArgumentParser(description='合成规则校准，不调用模型、不生成教师终审。')
p.add_argument('--result',help='独立评价产生的JSON；不提供时生成不含答案的测试请求')
p.add_argument('--out',required=True)
a=p.parse_args()
suite=read_json(ROOT/'tests/fixtures/calibration_20261021_2036.json')
output=evaluate(suite,read_json(a.result)) if a.result else blind_packet(suite)
save(a.out,output)
print(json.dumps({'output':a.out,'result':'checked' if a.result else 'blind_packet'},ensure_ascii=False))
if a.result and not output['all_passed']:raise SystemExit(2)
