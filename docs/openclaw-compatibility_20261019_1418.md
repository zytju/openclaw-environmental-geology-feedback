# OpenClaw版本兼容与权限配置

2026年10月19日重新核实，本机明确路径的OpenClaw命令返回2026.7.1-2 (0790d9f)，不再仅依据旧聊天或配置元数据猜测版本。默认PATH未找到该命令，但实际安装可从用户本机的命令包装器访问。这里不公开该机器的安装路径或配置内容。

| 目标 | 配置形式 | 证据与验证范围 |
|---|---|---|
| 2026.7.1-2 | agents.list数组，条目带id；agents.list[].skills | 官方v2026.7.1-2固定标签源码；本机隔离profile原生config validate通过 |
| 当前在线英文文档 | agents.entries对象，以对象键为id；可用ownership显式归属 | 官方当前Agent与Skills文档；未装新版运行时验证。不可用于2026.7.1-2 |

新版当前文档将多Agent隐式default改为显式归属；本项目所有运行均明确--agent，不依赖隐式路由，不创建学生直接登录或外部消息通道。在线翻译页仍可能保留list，不能据单个翻译页面判断版本兼容。

官方核验入口：

- [当前Agent配置](https://docs.openclaw.ai/gateway/config-agents/entries-and-multi-agent)
- [当前多Agent路由](https://docs.openclaw.ai/concepts/multi-agent)
- [Skills与可见性](https://docs.openclaw.ai/tools/skills)
- [工具权限与沙箱](https://docs.openclaw.ai/tools/multi-agent-sandbox-tools)
- [沙箱配置](https://docs.openclaw.ai/gateway/config-agents/sandbox)
- [当前Agent命令](https://docs.openclaw.ai/cli/agent)
- [固定2026.7.1-2配置Schema](https://github.com/openclaw/openclaw/blob/v2026.7.1-2/src/config/zod-schema.agents.ts)
- [固定2026.7.1-2多Agent文档](https://github.com/openclaw/openclaw/blob/v2026.7.1-2/docs/concepts/multi-agent.md)
- [固定2026.7.1-2 Skills文档](https://github.com/openclaw/openclaw/blob/v2026.7.1-2/docs/tools/skills.md)
- [固定2026.7.1-2 Agent命令](https://github.com/openclaw/openclaw/blob/v2026.7.1-2/docs/cli/agent.md)
- [历史版本发布记录](https://github.com/openclaw/openclaw/releases/tag/v2026.7.1-2)

基础来源在2026-10-16核验；2026-10-19重查当前entries文档及固定版本沙箱说明，并重新进行本机原生配置校验。在线文档不锁定某一安装版；历史标签用于保留兼容基准。CLI JSON封装适配支持顶层payloads和result.payloads两种结构，只接受一条JSON文本响应；实际provider封装尚需真实模型小样本确认。

## 只准备新profile

在仓库根目录执行，model值应先从目标OpenClaw实际可用模型中核实。下面的example-provider/example-model只是配置校验用标记，不能据此调用模型。

```bash
python3 -m egtool stage --out /tmp/eg-profile-NEW --layout legacy-list --model example-provider/example-model
```

该操作只创建全新的目录、两套角色workspace和配置，不写现有~/.openclaw、不拷贝密钥、不启动Gateway。当前文档布局用current-entries；不要同时放list与entries。共享Skills的优先级可能覆盖同名规则，因此只在独立workspace放置本项目允许的Skills，并核查实际加载结果。

准备目录中的openclaw.json是完整教学profile骨架，没有provider凭证、通道或真实学生材料。真实模型ID、认证和容器镜像由教师在正式部署批准后配置和核验。使用本轮生成的profile可做schema校验；它不是已完成安装与运行的凭证。

2026年10月16日的隔离profile目录检查曾确认：学生端可见eg-authenticity-anchor与eg-report-feedback，教师端可见eg-authenticity-anchor与eg-rubric-check。该版本CLI的eligible只表示环境条件满足，仍须同时检查blockedByAgentFilter与modelVisible；不能仅凭eligible=true判断某Skill对当前Agent可见。实际模型提示加载及工具阻断仍需后续验收。

## 正式运行前的确认与验收

先确认现用配置权威路径、备份和恢复办法，再由用户批准具体部署目录、模型和数据路由。保持旧实例不变，不执行doctor --fix、自动迁移、升级或重启现有服务。

在独立profile环境中运行目标版本的config validate，检查版本、skills加载和sandbox explain。随后用不含真实学生资料的样例检查：只能read；无法shell、浏览、发消息、跨会话或读其他Agent状态；workspace只读；容器无外网。目录隔离与SKILL.md本身不是安全边界，配置通过也不能代替实际阻断测试。

两个Agent的agentDir与workspace均分开；scope=session给每份报告和角色使用新的会话沙箱。包装程序每次生成UUID会话，不把学生材料写入共享workspace。实际provider可能通过宿主服务调用模型，容器network=none不等于模型数据不出主机，须核实并批准实际数据路由。

OpenClaw启动类命令可能初始化状态库；连帮助命令也可能触发本地状态处理。除只读版本核验外，后续检查一律显式设置OPENCLAW_CONFIG_PATH和OPENCLAW_STATE_DIR到新profile。勿在默认状态目录试跑未知命令。

## 本轮新增证据与限制

2026年10月19日，两个全新profile均用本机OpenClaw 2026.7.1-2 (0790d9f)校验：legacy-list返回valid=true且无警告；current-entries返回valid=false，agents为Invalid input。后者仅说明该旧版不接受候选布局，没有证明候选布局在任何新版可用。

current-entries的目标仅锁定2026年10月19日在线文档快照，未确定经实测的新运行时版本。10月23日前优先沿已装旧版进行独立验收，不为匹配在线文档自动升级或迁移。

请求已加入role_rules正文及SHA-256，降低ro路径不确定性对规则提供的影响。它不能证明模型遵循了规则，也不能替代原生Skill加载测试。固定版文档称ro工作区挂载于/agent，但Skills段落未完整说明所有ro情况，故保留待实际核验状态。

固定版文档说明默认Docker镜像需先构建，npm安装不带sandbox-setup.sh，应按官方来源安装方式准备；本轮未构建、启动或测试容器。可参考[固定版本沙箱说明](https://github.com/openclaw/openclaw/blob/v2026.7.1-2/docs/gateway/sandboxing.md)。部署批准后，应检查sandbox explain、实际读取Skill结果、尝试工具越权的阻断，以及profile/workspace前后新增文件；缺一不声称已完成隔离验收。

CLI meta中的durationMs与agentMeta.usage仅在存在且为非负数值时记录；缺值为null。本地墙钟时间不等于服务端计费时间。伪CLI测试只证明适配器按约定传参和解析，不证明真实provider兼容。
