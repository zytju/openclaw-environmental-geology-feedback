# Agent按需读取教学Skill

当前本机运行后端会过滤通用read工具。本版通过OpenClaw插件eg-skill-reader注册专用只读工具eg_skill_read，供Agent按任务读取本角色的Skill正文和参考文件。TOOLS.md只说明读取入口，不再预加载整份规则。

## 准备独立工作区

```bash
python3 -m egtool stage --out /PRIVATE/eg-profile-NEW \
  --layout legacy-list --model openai/gpt-5.6-sol --skill-loading on-demand
```

工作区保存角色Skill及资源校验清单，插件复制到该独立profile。OpenClaw模型插件需按本机实际安装状态配置。本机验证环境使用OpenClaw 2026.7.1-2与官方Codex插件2026.7.1-1；不通过关闭角色限制来获得文件访问。

## 读取范围

学生端可读取eg-authenticity-anchor和eg-report-feedback。教师端可读取eg-authenticity-anchor和eg-rubric-check。调用只接受技能名及SKILL.md或references下已登记的单个资源名。入口检查运行时角色、资源清单、实际路径、文件类型、大小和校验值；拒绝其他角色的专业Skill、路径跳转、符号链接及内容变化的文件。

每次工具返回完整正文及文件校验值。首次任务先读两个角色Skill，再按初稿或修订稿读取评分锚点、协议等必要参考。完整文件读取与规则采用分别核对，不能只凭技能列表可见认定已经读取。

## 用合成作业验证真实模型

```bash
python3 -m egtool synthetic-live --inputs /PRIVATE/synthetic-inputs \
  --intake /PRIVATE/synthetic-intake.json --count 6 \
  --config /PRIVATE/eg-profile-NEW/openclaw.json \
  --executable /ABSOLUTE/openclaw \
  --out /PRIVATE/serial-NEW --audit /PRIVATE/serial-audit-NEW \
  --confirmed-live-use
```

此入口只接收synthetic材料。双端逐份串行运行，每次使用独立会话，保存原响应、结构校验和实际读取证据。发生错误时停止，不盲目重试。已确认完成的响应可以单独核验和恢复；结果不确定的调用需先查明状态。

读取探针只把随机校验值写入允许读取的测试文件，请求中不给出答案。实际返回值、工具调用和文件正文对应后，才记为读取成功。连续运行另外检查完整反馈与教师复核，原始材料与模型记录均不进入公开仓库。

容器配置和专用读取入口的检查不替代全部生产隔离验收。处理真实作业的原入口继续要求独立审批和相应运行验证。

接口依据见OpenClaw官方[插件工具说明](https://docs.openclaw.ai/plugins/building-plugins)与[Codex动态工具说明](https://docs.openclaw.ai/plugins/codex-harness-reference/dynamic-tools)。实际支持范围以本机版本和本轮读取记录为准。
