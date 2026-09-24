# Hermes 隔离验收夹具准备

`scripts/hermes-evaluation-seed.py` 仅面向全新、独立的数据库。它通过现有 API 创建模型配置（或引用该隔离库中的已启用配置）、项目、模块、需求、知识、用例、需求关联和一条失败运行。脚本先确认项目、需求、知识和用例运行列表为空，要求题集版本为 `2026-09-23.1`，并逐一核对首条需求、知识及运行的主键都是 `1`。最后调用 Hermes 五个只读工具，要求每个工具返回 `ok` 与证据。

脚本不会删除或修改已有资产，也不会提交十道评测题。API 无法证明数据库在物理上与业务库隔离；运行者须先核对 Compose 数据库连接与卷，并显式传入 `--confirm-isolated-db` 和 `--allow-mutations`。任一步失败后脚本立即停止、不回滚已创建的数据；应保留报告排查，然后丢弃整个隔离数据库并从空库重建。不要在同一库重跑，因为 PostgreSQL 序列不会随资源删除而复位。

## 连接与凭据

隔离 Compose 的 Backend 在 Linux 宿主机仅监听 `127.0.0.1:39184`。从 Windows 使用 SSH 本地转发后，脚本访问本机的 `http://127.0.0.1:39184/api/v1`：

```powershell
ssh -N -L 39184:127.0.0.1:39184 user@host
```

在另一个 PowerShell 终端运行脚本。认证可用 `ATP_TOKEN` 或 `ATP_TOKEN_FILE`；也可用 `ATP_USERNAME` 加 `ATP_PASSWORD` 或 `ATP_PASSWORD_FILE`。配置文件方式避免把秘密放进命令行。创建模型配置时，设置 `ATP_HERMES_MODEL_PROVIDER`、`ATP_HERMES_MODEL_NAME`，以及非 Ollama 提供商所需的 `ATP_HERMES_MODEL_API_KEY` 或 `ATP_HERMES_MODEL_API_KEY_FILE`。OpenAI 兼容提供商还须设置 `ATP_HERMES_MODEL_ENDPOINT`。这些值不会写入脚本报告；模型端点须能从隔离 Backend 容器访问。

```powershell
$env:ATP_USERNAME = 'isolated-admin'
$env:ATP_PASSWORD_FILE = 'C:\private\atp-isolated-admin-password.txt'
$env:ATP_HERMES_MODEL_PROVIDER = 'openai_compatible'
$env:ATP_HERMES_MODEL_NAME = 'your-model-name'
$env:ATP_HERMES_MODEL_ENDPOINT = 'https://your-model-provider.example/v1'
$env:ATP_HERMES_MODEL_API_KEY_FILE = 'C:\private\model-api-key.txt'

.\.venv\Scripts\python.exe scripts/hermes-evaluation-seed.py `
  --base-url 'http://127.0.0.1:39184/api/v1' `
  --probe-url 'http://backend:8000/health' `
  --create-model-config `
  --confirm-isolated-db --allow-mutations `
  --report '.local-run/hermes-evaluation-seed.json'
```

如果隔离库已通过正常 API 创建并启用了模型配置，可用 `--llm-config-id <隔离库配置编号>` 代替 `--create-model-config`，无需设置模型配置环境变量。`--probe-url` 是 **Worker 容器内**可访问的隔离 Backend 健康地址；脚本只允许 `/health` 路径。用例对该地址发起 GET，确认实际响应是 HTTP 200，再用预设的 999 状态码断言使运行以 `failed` 结束。隔离环境应确认 `AI_HEALING_ENABLED=false`，避免失败运行触发额外的模型诊断。

报告只记录阶段、资源编号、运行状态与工具状态，不记录令牌、密钥、回答或来源正文。通过后从报告读取 `project_id`，按 [Hermes 固定题与模型规划验收](hermes-evaluation-acceptance.md) 先做预检，再显式执行十题及模型规划挑战题。脚本以管理员身份准备夹具与核查工具；viewer 角色矩阵、供应商用量和答案事实仍需另行验收。
