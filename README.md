# 基于OpenClaw的环境地质学案例诊断报告形成性反馈教学

## 2025级期中文献报告：学生本地课程包

推荐OpenClaw＋本人DeepSeek API。仅评三峡库区滑坡及灾害链，正文2000字以上，至少2篇研究性论文，建议中文、英文各1篇。报告通过问卷星提交；截图选交，若选交，1张截图单独上传。草图和证据卡均可缺席，仍给完整六维。

- [下载学生安装包](downloads/eg-student-kit_20261109_1710.zip)：只含学生启动器、两个学生Skill、协议和规则，不含教师角色、密钥或学生材料。
- [逐步图文指南](docs/student-guide_20261109_1710.md)（[PDF下载](downloads/student-guide_20261109_1710.pdf)）：下载、安装、自检、DeepSeek API、六维反馈、修订与提交。
- [启动器说明](student-native/README.md)及[验收记录与未完成条件](docs/native-verification_20261109_1710.md)。

**本次变更在分支codex/midterm-student-portal-20261109与PR #1，尚未合并主分支。没有已实测开放的全班公共URL。** 本地启动器真实调用OpenClaw 2026.7.1-2的学生Agent，所有模型工具禁用，加载两项学生Skill规则，并执行非阻断材料门槛、Schema及逐字引文检查。每次反馈使用新会话，不向学生提供教师凭据。

教师本机GPT已实测连接、六维反馈、缺两项可选材料、独立会话及越权请求拒绝。DeepSeek配置和本机兼容接口传输已验证，**没有真实DeepSeek Key，因此真实DeepSeek调用尚未验收**。66份合成测试不是66名真实学生部署结果。首次在本人电脑通过自检、真实DeepSeek连接和完整六维后，才算该电脑可用。学生拥有自己电脑的管理权限，本地包不能替代教师托管服务的强制权限控制。

先前[网页适配器方案](docs/student-portal-deployment_20261109_1300.md)保留作备选，它与本次原生OpenClaw启动器是不同路径；旧文档的截图要求已由本次选交规则更新。

## 历史教师流程与2026年10月验证记录

主分支更新 2026年10月21日  发布基线 v0.1.2-preview

面向树坪滑坡案例，由教师控制学生反馈和教师复核两个Agent，使用材料检查、专业反馈和量规复核三个Skill。程序保存原文、反馈、教师修改、复核和终审之间的版本对应。

## 已完成的本轮验证

- 144项本地Python测试、7项专用读取检查和66份离线模拟处理通过。
- 6份合成作业完成12次双端Agent运行，保留101次实际Skill文件读取记录。
- 发现一处最高等级依据偏宽，补充校准规则后，同一片段重新建议2级；教师修改稿另行复核并保留历史。
- 原18893教学服务已更新，原修订会话和用户默认配置保留。

本轮方法和范围见[真实运行记录](docs/live-verification_20261021_2121.md)。[GitHub自动测试](https://github.com/zytju/openclaw-environmental-geology-feedback/actions/workflows/tests_20261019_1418.yml)按当前提交查看。

## 先运行离线演示

仅需Python标准库，不调用模型，也不需要密钥。输出放在仓库之外的新目录。

```bash
python3 scripts/offline_smoke_20261019_1418.py
python3 scripts/offline_smoke_20261019_1418.py --count 66
python3 -m unittest discover -s tests -v
node plugins/eg-skill-reader/test.mjs
```

离线输出标为模拟，真实模型调用数为0，人工终审数为0，受益人数为空。课堂作品评分和问卷结果按独立材料报告。

## 按需读取教学Skill

当前本机后端过滤通用read工具。本版用专用只读工具eg_skill_read读取本角色已登记的Skill及参考文件，检查角色、路径和文件版本。TOOLS.md只说明入口，不再预加载整份规则。

```bash
python3 -m egtool stage --out /PRIVATE/eg-profile-NEW \
  --layout legacy-list --model openai/gpt-5.6-sol --skill-loading on-demand
```

stage准备独立配置和工作区，模型插件与认证按本机状态配置。操作及合成真实模型测试见[按需读取说明](docs/on-demand-skills_20261021_2121.md)。本机验证版本为OpenClaw 2026.7.1-2和官方Codex插件2026.7.1-1。Windows未测试。

## 教师修改与终审

教师可改写、新增或撤回问题，并调整维度依据。edit-template生成修改模板，apply-edits保留原稿并生成修改稿和完整记录。修改稿需要重新复核，旧批准不能沿用。终审及发放副本绑定本轮修改历史。具体步骤见[教师修改说明](docs/teacher-edits_20261021_2121.md)。

同一任务影响多个维度时，其他维度通过related_issue_ids关联已有任务，避免重复开列。教师核查事项与学生修订任务分别保留。等级建议不自动加总，正式成绩由教师决定。

## 使用入口

| 任务 | 文件或命令 |
|---|---|
| 组织教学与准备材料 | [教师手册](docs/teacher-manual_20261019_1418.md) |
| 阅读案例、量规和来源 | case-study/assignment_20261019_1418.md、rubric.json、sources.json |
| 安装角色与核验运行配置 | [兼容性说明](docs/openclaw-compatibility_20261019_1418.md)、egtool stage |
| 转换、材料核查与受控批处理 | egtool prepare、intake-template、batch |
| 修改、重新复核和终审 | egtool edit-template、apply-edits、final-template、release |
| 生成中文阅读版 | egtool reading-views |
| 按阶段汇总教师确认记录 | egtool summarize-finals |
| 复用本轮合成测试输入 | tests/fixtures/live-synthetic_20261021_2121/ |

完整报告按六维评价，片段只评价声明范围。未知来源先核查；模型处置建议、教师终审、实际发放和学习表现分别记录。真实作业批处理仍需完成目标环境的权限、跨会话及生产隔离验收，审批不会因合成测试自动通过。

## 获取版本与许可

本轮源码校验使用MANIFEST_20261021_2121.sha256。主分支包含按需读取和修改追溯功能；旧v0.1.2-preview标签及发布附件保留为历史基线。使用本轮功能请取主分支或日期对应的新交付包。旧清单和历史文档按当时版本追溯。

自编代码、规则、模板和模拟材料采用[MIT](LICENSE)，第三方资料见[权利说明](THIRD_PARTY_NOTICES.md)。公开仓库提供合成样例；学校原件、真实作业、身份表、会话和凭证保存在教师私有归档。
