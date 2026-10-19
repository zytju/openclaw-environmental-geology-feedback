# OpenClaw环境地质学形成性反馈

**v0.1.2-preview**

面向《环境地质学》树坪滑坡案例，由教师运行学生反馈与教师复核两个Agent，使用三个Skill完成材料门槛、六维形成性反馈及量规质控。

## 先运行离线演示

解压后，在包含本README的目录执行。无需安装Python依赖、OpenClaw、模型或密钥。本地已验证macOS上的Python 3.12与3.13；Linux将在配置的GitHub Actions中验证，当前尚无远程结果。其他版本和Windows未测试。

```bash
python3 scripts/offline_smoke_20261019_1418.py
```

默认处理3份原创模拟材料，自动寻找本次生成的intake，输出放在仓库之外的系统临时目录。需要66份时：

```bash
python3 scripts/offline_smoke_20261019_1418.py --count 66
python3 -m unittest discover -s tests -v
```

输出is_simulated=true，人工终审数为0，受益人数为空；它只证明离线程序流程，不是专业模型反馈或课堂效果。运行目录显示在终端中，不自动覆盖旧结果。

## 使用入口

| 需要做什么 | 入口 |
|---|---|
| 安装三个Skill到新工作区、准备独立Agent | [教师手册](docs/teacher-manual_20261019_1418.md)、[OpenClaw兼容性](docs/openclaw-compatibility_20261019_1418.md) |
| 阅读案例、核验来源与评价规则 | [学生任务](case-study/assignment_20261019_1418.md)、case-study/sources.json、rubric.json |
| 批量转换固定Markdown并生成未签认审核表 | egtool prepare、intake-template，见教师手册 |
| 教师终审、选择实际发放的问题、汇总学生问题 | egtool final-template、release、summarize-finals |
| 查看真实完成与未验证事项 | [测试报告](docs/test-report_20261019_1418.md)、[审计更正](docs/audit-correction_20261019_1418.md) |
| 查看本预览版的发布说明 | [发布说明](docs/release-notes_20261019_1418.md) |

## 仓库结构

| 目录 | 内容 |
|---|---|
| skills/ | eg-report-feedback、eg-rubric-check、eg-authenticity-anchor，含自包含校验器及协议 |
| agents/ | eg-student-feedback、eg-teacher-review及分版本配置示例 |
| case-study/ | 案例、六维量规、来源索引、模板及明确标为模拟的样例 |
| schemas/ | 协议1.1.0：提交、门槛、反馈、复核、终审、发放与汇总 |
| egtool/、scripts/、tests/ | Python标准库程序、离线演示与测试 |
| docs/ | 教师操作、隐私、兼容性、实际验证与结题证据边界 |
| .github/workflows/ | 自动测试配置；尚未在GitHub执行 |
| history/ | 0.1.0 Skills和0.1.1交付快照，仅用于追溯，旧说明不代表当前状态 |

## OpenClaw兼容性与边界

本机已核验2026.7.1-2 (0790d9f)，legacy-list配置可被其原生Schema接受；entries候选被该旧版拒绝。current-entries只对应2026年10月19日在线文档，没有经验证的新运行时目标。

将指定Skill目录复制到全新工作区skills/，并按手册使用独立profile。stage只准备文件，不启动服务。每次请求同时带有角色规则正文和哈希，但仍需实际检查原生Skill读取、真实模型、Docker工具权限、会话存储及教师专业判断。当前不保证直接用于真实课堂或工程安全判断。

评价六维为问题识别、证据提取、推理链完整性、灾害链、不确定性、防治建议匹配。完整报告与片段必须声明范围，范围外不判缺项。未知来源先交教师核查，AI质控统计与教师确认的学生问题分开。协议1.0.0输入须显式迁移、重新审核；旧哈希和旧反馈不可直接沿用。

## 许可与发布状态

自编代码、规则、模板和模拟值采用[MIT](LICENSE)，版权署名为OpenClaw EG teaching project contributors。第三方论文和数据保留各自许可，见[第三方说明](THIRD_PARTY_NOTICES.md)。公开包不含学校原件、问卷图、学生作业、身份表、密钥、真实会话或真实监测文件。

本次准备了GitHub预览包，未创建远程仓库、上传或发布Release，未部署OpenClaw。负责人确认后可将本目录内容上传并标为预发布；完成真实链路和课堂证据后再更新版本。
