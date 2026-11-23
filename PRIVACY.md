# 隐私与外部传输 / Privacy and data flow

- 原始晶体文件和本机运行记录默认在用户电脑上处理。脚本不以维护者邮箱接收数据，也不自动提交反馈。
- 使用云端 AI 时，提供给助手的文字、文件或图片可能按该平台的设置传输和保存；“本地求解器”不等于整段对话不出网。敏感项目应先确认机构政策和平台设置。
- 官网 checkCIF 会将所选 CIF（通常含结构因子、精修输入及实验说明）传给 IUCr。授权只覆盖用户明确同意的数据及用途；不假定服务的保密、留存或删除承诺。拒绝上传时可继续本地工作，但官网 PDF 缺项要说明。
- 安装依赖和可选模型时会联系相应官方来源。可选识图模型需单独确认代码、权重和训练数据条款，不随本包分发。
- 本地完整日志可能包含绝对路径、原子坐标、化合物身份和敏感说明。公开反馈使用最小脱敏包，并由用户检查内容；不要上传完整运行目录、账号密码或许可证凭据。

Local solvers do not imply that a connected AI service is offline. Review the AI platform's data handling and institutional rules. IUCr validation transmits the selected CIF, potentially including reflections and embedded refinement instructions, only with scoped authorization. This project makes no retention/confidentiality promise on behalf of external services. Feedback is not automatically sent; inspect and minimize it before sharing. No research data are required in a public issue.
