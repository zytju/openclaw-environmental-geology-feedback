# GitHub上传与在线测试核验

核验日期：2026年10月19日，Asia/Shanghai。

仓库：[zytju/openclaw-environmental-geology-feedback](https://github.com/zytju/openclaw-environmental-geology-feedback)。已确认账户zytju及仓库写入权限，仓库为public。

## 文件与版本

- 初次完整上传提交：8a46df0b68e00ca24d06773a35acc59f49be151b；133个文件与审定版本逐字节一致，Git tree为35d449e48609a385427101c2161c7b2e6e40dc10。连接器先创建README以初始化空仓库，再完整发布目录，因此远端提交SHA不同于本地准备提交bbed667954228724d0a7a280e7ee3651b2be7d6a，文件内容相同。
- 暂停后核验提交：b697364be81fcbf85d02c8396236e37544b95f97。133个文件均通过连接器重新读取，并在本地重算Git blob SHA与SHA-256。132个文件与初始包一致，README的两次人工修改已保留，未恢复旧标题或开头。
- 本轮新增发布文档、清单和工作流，并更新README中的上传、CI状态；反馈代码、Skill与模拟数据未更改。
- 当前清单为MANIFEST_20261019_1726.sha256，覆盖本次源码除清单自身之外的全部文件。原MANIFEST_20261019_1418.sha256只用于初始上传提交或14:18原审定包，后续README修改使它不再适合校验当前目录。
- 原审定ZIP的SHA-256为4d9f7ba1a41c7401a71a42ea06bc8f37a43fe060b6da8f3712ca96f5c25f9205，原包未修改。Release附件从测试通过的发布提交直接导出，具有独立文件名与校验值。

逐文件核验见remote-content-checks_20261019_1726.json。此文件对应上面明确的核验提交，不声称覆盖随后新增的发布文件；后者由当前清单及发布工作流检查。

## 远端测试

[初次完整上传测试](https://github.com/zytju/openclaw-environmental-geology-feedback/actions/runs/39216799886)和[暂停后最新提交测试](https://github.com/zytju/openclaw-environmental-geology-feedback/actions/runs/39228222085)均成功。已读取四组job日志，确认每组100项测试、66份模拟批处理成功，is_simulated=true、real_model_calls=0、human_final_reviews=0。精简机器记录见ci-evidence_20261019_1726.json。

发布工作流只处理本仓库main分支push触发且成功完成的Offline tests，检出被测试的明确提交后验证当前清单，再创建v0.1.2-preview和源码ZIP、校验文件。只有发布job获得本仓库临时contents:write权限，不使用本地登录凭据。已有Release时不覆盖标签或附件。发布是否完成以[Release页面](https://github.com/zytju/openclaw-environmental-geology-feedback/releases/tag/v0.1.2-preview)和[工作流记录](https://github.com/zytju/openclaw-environmental-geology-feedback/actions)为准。

## 仍未验收

真实OpenClaw模型、原生Skill正文读取、容器工具阻断、真实会话隔离、教师专业校准、课堂实施与教学效果仍未验收。未部署现有OpenClaw服务，未升级运行时，未取得真实监测文件。技术和模拟测试不能替代这些验证。

学校材料、sources同步参考、学生资料、密钥、本地配置和私有审计目录均未进入公开内容。原有审计中一个学校DOCX哈希变化的事实与原因未确认状态仍保留，未恢复或覆盖原件。
