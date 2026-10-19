# GitHub预览发布准备

建议标签：v0.1.2-preview，标为Pre-release。仓库名可用openclaw-environmental-geology-feedback；这只是建议名称，尚未创建任何远程仓库或链接。

## 上传内容

解压预览包，使用含README.md的仓库目录。提交该目录内的源码、skills、agents、case-study、schemas、tests、scripts、docs、history，以及隐藏的.github和.gitignore。Mac的Finder可按Command+Shift+.显示隐藏文件。

不要上传外层工作目录、private-audit、本机profile、学校原件、学生材料、身份映射、真实运行记录、问卷细项或密钥。ZIP作为Release附件可以保留，但不能替代仓库中可浏览的源码。若新建空仓库，不必另外生成会冲突的README或LICENSE。

本包自编部分已统一MIT；第三方资料保留各自许可。源文件已明确披露未取得真实监测文件，包含的数值序列均为模拟。原件审计更正见audit-correction，历史校验失败或限制不隐藏。

## 自动测试

.github/workflows/tests_20261019_1418.yml在push、pull_request或手动触发时配置Ubuntu/macOS、Python 3.12/3.13矩阵，执行标准库测试与66份模拟。无需模型密钥或OpenClaw服务，不调用真实模型；工作流的代码检出和Python准备仍需要GitHub网络。

本地已完成两个Python版本的100项测试和各66份模拟，Actions尚未远程执行。首次上传后查看Actions实际结果；不要在它运行前添加“CI已通过”的徽章或结论。不把CI流程称为Docker权限或专业反馈验收。

配置依据于2026年10月19日核验的官方来源：[Checkout v7](https://github.com/actions/checkout/tree/v7)、[Setup Python v7](https://github.com/actions/setup-python/tree/v7)、[Workflow语法](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)。采用contents:read，不持久保存检出凭据，不配置模型密钥。

## 发布文字

Release标题可用“v0.1.2-preview：环境地质学形成性反馈开发预览”，正文使用release-notes。不要称为生产稳定版、已部署课堂系统或已有教学成效。

真实OpenClaw链路、原生Skill读取、容器阻断、会话存储和教师专业校准后，再决定课堂可用版本。10月23日实施后按真实材料更新，不上传学生原件。当前仅准备文件，没有执行GitHub上传、发布或部署。
