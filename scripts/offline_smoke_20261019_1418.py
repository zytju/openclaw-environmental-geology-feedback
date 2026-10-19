#!/usr/bin/env python3
"""One-command synthetic demonstration; never selects the OpenClaw backend."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from egtool.contracts import ContractError, require
from egtool.pipeline import make_demo, run_batch


def offline_demo(count=3, out=None):
    require(type(count) is int and 1 <= count <= 66, 'DEMO_COUNT_1_TO_66')
    if out is None:
        base=Path(tempfile.mkdtemp(prefix='openclaw-eg-preview-'))
    else:
        base=Path(out).absolute()
        require(not base.exists(), 'OUTPUT_EXISTS')
        base.mkdir(parents=True, mode=0o700)
    demo=make_demo(base/'demo', count)
    intakes=list(demo.glob('intake_*.json'))
    require(len(intakes)==1, 'DEMO_INTAKE_FILE_REQUIRED')
    summary=run_batch(demo/'submissions', intakes[0], base/'run')
    require(summary['is_simulated'] and summary['backend']=='mock', 'SIMULATION_REQUIRED')
    return {'package_version':'0.1.2-preview','backend':summary['backend'],
        'is_simulated':summary['is_simulated'],'attempted':summary['attempted'],
        'valid_teacher_model_reviews':summary['valid_teacher_model_reviews'],
        'human_final_reviews':summary['human_final_reviews'],
        'confirmed_beneficiaries':summary['confirmed_beneficiaries'],
        'real_model_calls':0,'output_directory':str(base.resolve())}


def main():
    p=argparse.ArgumentParser(description='运行原创合成材料的离线演示，无需OpenClaw或密钥，不调用真实模型。')
    p.add_argument('--count',type=int,default=3)
    p.add_argument('--out',help='可选的全新输出目录，不能已存在；默认使用仓库外系统临时目录')
    a=p.parse_args()
    try:
        print(json.dumps(offline_demo(a.count,a.out),ensure_ascii=False,indent=2))
    except (ContractError,OSError,ValueError) as exc:
        print('停止：'+str(exc),file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
