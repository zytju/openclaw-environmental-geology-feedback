# 协议与材料索引

本版协议为1.1.0，项目版本0.1.2-preview。先读[rubric.json](rubric.json)的范围与等级对应，再读[case-facts.json](case-facts.json)和[sources.json](sources.json)。事实指针可追溯不等于解释必然正确。

- [submission.schema.json](submission.schema.json)：report_scope、assessed_dimensions、P段、A分析、E证据卡及修订清单。
- [teacher-intake.schema.json](teacher-intake.schema.json)：教师独立核查，绑定提交哈希，不由学生自填。
- [gate.schema.json](gate.schema.json)：程序门槛，eligible/needs_material/teacher_hold。
- [feedback.schema.json](feedback.schema.json)：学生端六维反馈；范围外not_in_scope。
- [teacher-review.schema.json](teacher-review.schema.json)：教师端模型复核，尚非人工终审。
- [teacher-final.schema.json](teacher-final.schema.json)：人工签认和实际发放的问题清单。
- [release.schema.json](release.schema.json)：教师选定问题的本地发放副本。
- [human-summary.schema.json](human-summary.schema.json)：按阶段与范围汇总人工终审记录。
- [run.schema.json](run.schema.json)：技术运行与AI反馈质控计数、每次调用耗时和可获得的用量。

辅助检查必须提供一条teacher-intake对象；批处理使用intake数组。不要拿旧gate替代intake。仅结构校验成功不能证明科学正确。

源注册表以教师核验的本地副本为准；新增教材来源后需同步到三个Skill及新profile，并重新核查intake。历史1.0.0输入必须显式迁移并重新审核，旧反馈和哈希不可直接沿用。

gate文件中的status位于根对象；包装程序将整个gate对象放进validated_material_gate。辅助脚本只接收提交与intake重算门槛，不接收模型自报gate。
