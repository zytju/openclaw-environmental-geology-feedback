import argparse
from pathlib import Path
import sys
from .contracts import ContractError
from .pipeline import make_demo, stage, run_batch, OpenClawBackend
from .intake import prepare, intake_template, upgrade_submission, csv_ids
from .finalize import final_template, release, summarize_finals
from .contracts import DIMENSIONS


def main():
    p=argparse.ArgumentParser(description="教师控制的环境地质学反馈工具；默认不调用真实模型。")
    sp=p.add_subparsers(dest="cmd",required=True)
    d=sp.add_parser("demo");d.add_argument("--out",required=True);d.add_argument("--count",type=int,default=66)
    st=sp.add_parser("stage");st.add_argument("--out",required=True);st.add_argument("--layout",choices=["legacy-list","current-entries"],required=True);st.add_argument("--model",required=True)
    b=sp.add_parser("batch");b.add_argument("--inputs",required=True);b.add_argument("--intake",required=True);b.add_argument("--out",required=True)
    b.add_argument("--backend",choices=["mock","openclaw"],default="mock");b.add_argument("--only",help="仅在新运行目录重试逗号分隔的匿名编号")
    b.add_argument("--executable");b.add_argument("--config");b.add_argument("--approval-file");b.add_argument("--confirmed-live-use",action="store_true")
    pr=sp.add_parser('prepare', help='将固定格式Markdown转换为提交JSON和未签认审核表')
    pr.add_argument('--markdown', required=True);pr.add_argument('--out', required=True)
    it=sp.add_parser('intake-template', help='批量生成哈希绑定、全部未勾选的教师审核表')
    it.add_argument('--inputs', required=True);it.add_argument('--out', required=True)
    up=sp.add_parser('upgrade-submission', help='显式迁移1.0.0输入；旧审核表和反馈不可沿用')
    up.add_argument('--submission', required=True);up.add_argument('--out', required=True)
    up.add_argument('--report-scope', choices=['full_report','excerpt'],required=True);up.add_argument('--dimensions')
    for name in ('final-template', 'release'):
        q=sp.add_parser(name,help='生成未签认终审模板' if name=='final-template' else '按教师签认清单生成本地发放包')
        for flag in ('submission','intake','feedback','teacher-review','out'):
            q.add_argument('--'+flag,required=True)
        if name=='release':q.add_argument('--decisions',required=True)
    sm=sp.add_parser('summarize-finals',help='按阶段汇总教师确认的学生问题，与AI质控统计分开')
    sm.add_argument('--records',required=True);sm.add_argument('--out',required=True);sm.add_argument('--stage',choices=['draft','revision'],required=True)
    a=p.parse_args()
    try:
        if a.cmd=="demo":
            print(make_demo(a.out,a.count));return
        if a.cmd=="stage":
            print(stage(a.out,a.layout,a.model));return
        if a.cmd=='prepare':print(prepare(a.markdown,a.out));return
        if a.cmd=='intake-template':print(intake_template(a.inputs,a.out));return
        if a.cmd=='upgrade-submission':
            dims=csv_ids(a.dimensions) if a.dimensions else DIMENSIONS[:] if a.report_scope=='full_report' else []
            print(upgrade_submission(a.submission,a.out,a.report_scope,dims));return
        if a.cmd=='final-template':
            print(final_template(a.submission,a.intake,a.feedback,a.teacher_review,a.out));return
        if a.cmd=='release':
            print(release(a.submission,a.intake,a.feedback,a.teacher_review,a.decisions,a.out));return
        if a.cmd=='summarize-finals':
            r=summarize_finals(a.records,a.out,a.stage);print('human_final_reviews='+str(r['human_final_reviews'])+' simulated='+str(r['is_simulated']));return
        backend=None
        if a.backend=="openclaw":
            if not all([a.executable,a.config,a.approval_file]):raise ContractError("LIVE_PROFILE_ARGUMENTS_REQUIRED")
            backend=OpenClawBackend(a.executable,a.config,a.approval_file,a.confirmed_live_use)
        r=run_batch(a.inputs,a.intake,a.out,backend,a.only.split(",") if a.only else None)
        print(f"backend={r['backend']} simulated={r['is_simulated']} attempted={r['attempted']} valid_teacher_outputs={r['valid_teacher_model_reviews']} human_final=0")
        if r['pending_or_failed']:sys.exit(2)
    except (ContractError,OSError,ValueError) as e:
        print("停止："+str(e),file=sys.stderr);sys.exit(1)


if __name__=="__main__":main()
