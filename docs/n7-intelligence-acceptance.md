# N7 智能中枢真实数据验收

该脚本验证“临时项目 → 模块 → 需求/知识/用例 → 需求解析与检索 → Hermes 来源引用 → 清理”的链路。blank 项目没有模块时，脚本会显式创建一个临时模块。Hermes 查询只读取当前项目和已发布的全局知识，不会自动修改测试资产；来源响应包含项目上下文、匹配词、脱敏摘要和可回看的路径。

脚本会创建并删除数据，必须显式传入 --allow-mutations。凭据只从环境变量读取，不要把密码、Token 或带凭据的 URL 写入命令行、仓库或证据文件。

## Windows PowerShell

    $env:ATP_USERNAME = '<admin-or-engineer>'
    $env:ATP_PASSWORD = '<password>'
    $env:ATP_VIEWER_USERNAME = '<ordinary-project-user>'
    $env:ATP_VIEWER_PASSWORD = '<password>'

    python scripts/n7-intelligence-acceptance.py --base-url 'http://127.0.0.1:8000/api/v1' --allow-mutations --require-role-matrix --report 'docs/evidence/n7-intelligence-acceptance-YYYY-MM-DD.json'

加入 `--require-ai` 后，脚本要求全局管理员账号，并先读取已保存的配置（不会读取或输出 API Key），再依次调用模型列表、连接测试和临时项目上的 AI 用例草稿生成。使用 `--llm-config-id <id>` 或环境变量 `ATP_LLM_CONFIG_ID` 选择配置；`--require-vision` 可要求配置和发现的模型声明多模态能力，`--require-thinking` 可要求保存的高级参数包含 `thinking`、`enable_thinking` 或 `reasoning_effort`。没有受控模型配置时该项应保持失败或跳过，不能将本地检索结果写成真实模型通过。

也可以使用 ATP_ACCEPTANCE_BASE_URL、ATP_TOKEN 或 ATP_USERNAME/ATP_PASSWORD 配置连接信息。报告只记录脱敏 endpoint、资源 ID、检查状态和有限长度说明，不记录密码、Token、Cookie、请求正文或响应正文。

2026-08-25 q19 基础数据证据：[`docs/evidence/n7-intelligence-acceptance-2026-08-25.json`](evidence/n7-intelligence-acceptance-2026-08-25.json) 为 `partial`；需求/知识/用例创建、详情读取、Hermes 三类来源引用和清理均通过，普通 viewer 矩阵与真实 AI 草稿未启用。完整 N7 门禁仍需受控模型和普通角色账号。

## 验收出口

- editable-retrieval：需求解析返回可编辑验收标准，需求和知识可按项目与关键词读取。
- hermes-sources：Hermes 返回 knowledge、requirement、case 三类来源，来源编号、匹配摘要和项目范围路径可回看。
- role-matrix：普通项目成员可以查询所属项目来源，但不能创建需求；使用 --require-role-matrix 才能把缺少普通账号视为失败。
- ai-model-preflight：只有传入 `--require-ai` 并通过保存配置、模型列表、连接测试，且满足显式多模态/思考门槛时才算通过；报告只记录配置 ID、供应商、模型名、能力布尔值和发现数量。
- ai-draft：只有传入 `--require-ai` 并收到真实模型草稿时才算通过，否则报告为 partial。
- cleanup：临时项目删除后再次读取必须返回 404；清理失败时优先处理残留资源。

命令入口：

    make n7-intelligence-acceptance ARGS="--base-url ... --allow-mutations --require-role-matrix [--require-ai --llm-config-id ... --require-vision --require-thinking] --report ..."
