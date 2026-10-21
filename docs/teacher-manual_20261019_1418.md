# 教师使用手册

实施日2026年10月23日。完整流程是学生独立分析→教师材料核查→学生端反馈→教师端模型质控→人工终审→发放→学生修订。模型复核不替代教师，输出结构合格不等于专业正确。

## 整理材料

教师私下保存身份映射，公开与模型输入仅使用S001—S066。Word、PDF和草图仍需核对转写；本版不做自动OCR或解析宏。使用case-study/submission-template_20261019_1418.md中的固定格式，可由学生按格式填写、教师核查，减少逐份拆段和手写JSON。不要把真实材料保存在公开仓库中。

```bash
python3 -m egtool prepare --markdown /PRIVATE/S001.md --out /PRIVATE/new-S001
python3 -m egtool intake-template --inputs /PRIVATE/submissions --out /PRIVATE/intake_20261019_1418.json
```

第一行的--markdown也可指向包含1至66份固定格式Markdown的目录，一次输出全部提交JSON和合并intake数组，重复编号会在写入前中止；第二行适合已汇集的最多66份JSON。两者自动计算哈希，但四个审核项全部为false，reviewer_code=T000，日期NOT_REVIEWED。教师实际核查材料可读、摘录来源、身份线索及是否允许反馈后，填写自己的T编号、实际日期，才逐项改true。不能批量假勾选。修订稿另核查previous_feedback_verified。

规范化哈希只消除JSON键顺序、缩进等序列化差异；正文空格、Unicode NFC/NFD、数值或字形变化可能改变哈希。本版保留原始文字以便逐字锚定，不声称各种文档格式变化都不影响哈希。

## 范围、来源和旧版迁移

full_report的assessed_dimensions按固定顺序列六维。excerpt只列本轮实际要评的维度；未列维度not_in_scope，不要求学生为它补交。范围内完全缺少内容才是absent。

现有source_id为ZOU2021、WEN2017、NCDC2016、NCDC2020、SIMULATION；SIMULATION不是真实监测。可以引用教材和讲义，但教师须先核查并登记来源、定位与使用条件，同步sources.json到三个Skill及新profile，必要时补case-facts条目。未登记来源进入teacher_hold，不丢学生编号；不为凑通过而改成不相干的已有source_id。

```bash
python3 -m egtool upgrade-submission --submission /PRIVATE/old.json --report-scope excerpt --dimensions reasoning_chain,uncertainty --out /PRIVATE/new.json
```

迁移产生协议1.1.0和新哈希，需要重新intake。旧1.0.0 gate、反馈和终审记录留作历史，不直接改版本号冒充新结果。

## 模型与批处理

先运行离线mock。真实模型仅在用户批准独立部署，且完成模型、容器、工具、数据路由核验后使用：

```bash
python3 -m egtool batch --backend openclaw --inputs /PRIVATE/submissions --intake /PRIVATE/intake.json --out /PRIVATE/new-run --executable /ABSOLUTE/openclaw --config /PRIVATE/new-profile/openclaw.json --approval-file /PRIVATE/profile-approval.json --confirmed-live-use
```

串行处理，双角色分别新UUID；66份完整通过最多132次调用。首次失败不自动重试；用新的输出目录和--only S005,S009选择重跑，不能重复计人数。退出0只表示协议处理完成；2表示存在失败或暂缓；1表示前置问题。这些状态都不是成绩或成效。

每条calls记录本机wall_seconds、协议是否通过、CLI有提供时的duration与token数；没提供记null，绝不按0消耗解释。mock耗时不能估算真实模型速度。费用需实际模型价目及账单，程序不编造金额。人工核查与终审耗时另由教师实测。当前不保存无效原始输出；诊断主要靠错误码与合成材料重现。

## 人工终审与发放

```bash
python3 -m egtool final-template --submission /PRIVATE/S001.json --intake /PRIVATE/S001-intake.json --feedback /PRIVATE/S001-feedback.json --teacher-review /PRIVATE/S001-teacher.json --out /PRIVATE/S001-decision.json
python3 -m egtool release --submission /PRIVATE/S001.json --intake /PRIVATE/S001-intake.json --feedback /PRIVATE/S001-feedback.json --teacher-review /PRIVATE/S001-teacher.json --decisions /PRIVATE/S001-decision.json --out /PRIVATE/new-S001-release
python3 -m egtool summarize-finals --records /PRIVATE/releases --stage draft --out /PRIVATE/new-human-summary
```

这里intake是单条对象，不是数组。final-template默认未审、未批准。教师逐条检查科学解释和量规，填写human_review_complete、actual reviewed_at（含时区）、真实T编号及comment；选择released_issue_ids及confirmed_student_problem_dimensions，再决定approved_for_release。模型hold时人工放行需要记录理由。

release只在本地生成教师选定的学生问题，拒绝发放severity=teacher_check事项，不带草稿等级或其他教师专用内容。不自动发送给学生。教师可用edit-template与apply-edits改写、新增或撤回问题，保留原反馈和修改历史，重新复核后完成本轮终审。操作见[教师修改与追溯](teacher-edits_20261021_2121.md)。

优先发放少量核心、可完成的问题，数量由教师按本次任务决定，不能把18条上限当目标。修订稿previous_issue_ids只填实际发放的released_issue_ids，学生逐项写采纳、部分采纳或拒绝的证据理由。教师核对上轮发放原件后勾选previous_feedback_verified。另发的人工建议须纳入教师维护的完整发放清单，不能遗漏追溯。

summarize-finals按阶段、学生去重，重复记录先由教师选定有效版本。它汇总的是人工填写记录，不证明教师真的完成了优质核查；已生成反馈包也不证明学生收到。AI质控问题数与教师确认的学生问题分开，每维使用实际评价范围分母，受益人数仍需真实参与证据。

## 立项输出形式对应

| 立项表述 | 当前字段或环节 |
|---|---|
| 成立的判断 | 每维basis，承认已有证据支持部分 |
| 证据不足 | issues.problem、evidence_card_ids与citations |
| 推理断点 | rationale与原文anchor |
| 修订建议 | revision_action与check_question |
| 边界提醒 | uncertainty与boundary_reminder |

保存原始作品、转换核对、intake、gate、模型版本与参数、源码校验值、AI原输出、教师终审、实际发放和修订记录。私有归档不进GitHub。正式成绩、专业判断与效果解释由教师负责。

## 专业校准待确认

纯文字文献证据没有数值时，不应为满足模板而编造单位与时段；具体等级由教师按实际适用的量规条目校准。报告引用一个“待核查命题”不自动表示学生接受该命题；教师需看上下文。声明full_report却正文称片段时先确认范围，修正后重新绑定哈希。
