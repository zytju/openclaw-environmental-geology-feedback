# Agent与Skills试运行后更新

2026年10月21日，在b6576fd8ab9532fe772f3180306f1986bfcb987d之后继续完善两个教学角色、三个Skill的协作入口和教师侧程序。反馈、复核、教师终审等协议仍为1.1.0，v0.1.2-preview发布基线保留。

## 评分与修订复评

学生反馈和教师质控Skill新增自包含评分锚点：核心断言与末段限制并存、治理建议与实施陈述、达到基本要求与最高等级。案例说明已采用判断及适用条件，并加入否定句和范围变化等对照，避免按关键词套级。

修订稿先核对教师实际发放任务，再检查修改位置、正文证据、采纳决定与理由、仍有的问题。合理部分采纳或拒绝可以实质回应任务。完成旧任务不自动提高所有维度等级，仍检查原问题延续及新问题。程序输入会同时携带必要参考正文和校验值。

## 程序生成阅读版

从通过校验的反馈与复核原件生成简短概览和完整依据。概览保留全部实际任务，教师概览保留低于最高等级时的判断依据；详细原因、核查问题、来源和原文仍保存在依据文件及JSON原件。学生概览隐藏数值等级和技术字段。教师核查项与学生任务分开。

```bash
python3 -m egtool reading-views \
  --submission /PRIVATE/submission.json \
  --intake /PRIVATE/intake.json \
  --feedback /PRIVATE/feedback.json \
  --teacher-review /PRIVATE/review.json \
  --decisions /PRIVATE/teacher-final.json \
  --out /PRIVATE/reading-NEW
```

不提供decisions时显示待教师终审；提供时校验提交、反馈、复核、稿次和评价范围的对应关系。未签认、旧版或不对应记录不能更新页面状态。程序只读实际终审决定，不替教师签认，也不把本地文件生成写成学生已经收件。

## 规则加载与运行配置

stage生成独立工作区时同时写入全局、默认和角色只读配置，并从Skill原件生成TOOLS.md。其EG_CONTEXT_VERSION绑定Skill正文和参考文件的校验值；生产调用前检查预加载文件是否与当前源码一致。缺失或过期时停止。TOOLS.md由本机OpenClaw作为上下文加载，不需要模型执行文件读取或shell命令。

本机两个角色的原生文件读取探针均未通过：当前没有可用read工具。此状态单独保留，不由预加载成功替代。新增受控预加载方式核验完整规则版本与未截断加载；不扩大工具权限。容器检查验证网络、只读根文件系统、绑定目录、角色目录对应及无特权配置。容器参数通过仍不等于原生工具和跨会话访问的完整验收。

```bash
python3 scripts/runtime_audit_20261021_2036.py \
  --executable /PATH/TO/openclaw \
  --config /PRIVATE/eg-profile/openclaw.json \
  --layout legacy-list \
  --docker /PATH/TO/docker \
  --out /PRIVATE/runtime-audit-NEW.json
```

此命令只读配置和本profile活动容器，不调用模型，不自动修改隔离审批。模型服务连接与容器内部网络分开；network=none仅描述被检查容器。

## 回归检查

本轮本地125项标准库测试、66份合成材料流程已通过。新增25项覆盖阅读版任务保留、学生与教师事项区分、终审状态绑定、过期记录拒绝、输入转义、预加载版本和容器目录边界。既有100项继续执行。

十个合成校准案例包括本次两处误判和不同表述的对照。独立评价只接收不含预设答案的测试包；评价结果与预期逐项对比，理由另行核查。该验证独立于OpenClaw的实际模型和运行环境验收，不作为课堂成效。

```bash
python3 -m unittest discover -s tests -v
python3 scripts/offline_smoke_20261019_1418.py --count 66
python3 scripts/calibration_20261021_2036.py --out /PRIVATE/blind-request-NEW.json
python3 scripts/calibration_20261021_2036.py \
  --result /PRIVATE/independent-results.json --out /PRIVATE/calibration-check-NEW.json
```

仓库只提供合成测试片段与规则，不附带用户会话、截图、人工回复、凭证或学校原件。独立评价和运行证据保存在本地更新包。GitHub四组检查按当前提交核对。
