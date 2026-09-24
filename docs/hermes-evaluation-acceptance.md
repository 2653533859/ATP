# Hermes 固定题与模型规划验收

`scripts/hermes-evaluation-acceptance.py` 对显式指定的项目运行 `hermes-core-v2` 固定题，并额外运行一道确定性路由不会命中的模型规划挑战题。默认只读取评测集和项目元数据；传入 `--execute` 才提交问题。脚本不创建、修改或删除业务资产，但执行模式会创建 Hermes 会话、审计记录，并可能调用收费模型。报告只保留题号、模式、工具状态、结果和原因码，不保存回答、来源正文、令牌或密码。

## 环境前置

1. 使用独立数据库和专用项目，通过正常 API/业务流程准备可访问的 `case` 运行编号 1、需求编号 1、知识编号 1、需求—用例关联、近期失败任务与质量趋势，以及匹配“登录”的项目来源。不要在现有业务库强行改写主键。
2. 项目绑定已启用的模型配置；验收账号具有项目 viewer 权限。预检只能确认绑定字段，不能证明模型可用或夹具齐全。
3. Backend 部署当前题集版本 `2026-09-23.1`。旧 Backend 会被版本门禁拦下。发布机在 2026-09-23 的只读核对仍为 `bdb84286`，尚未部署本契约。
4. 使用独立账号或短期令牌，并核对已发布的全局知识不会误充当前项目的预期来源。

全新独立数据库可按 [夹具准备说明](hermes-evaluation-seed.md) 使用正常 API 创建并核对固定编号资产。隔离 Compose 的 Backend 仅在 Linux 宿主机 `127.0.0.1:39184` 监听；从 Windows 运行时，先用 SSH 本地转发该端口到本机 `127.0.0.1:39184`。下面的地址是此隔离环境示例，其他部署按实际转发端口替换。

## 运行

在 Windows 工作区，使用 `ATP_TOKEN`，或使用 `ATP_USERNAME` 与 `ATP_PASSWORD`。不要把认证值放在命令行、报告路径或仓库中。若夹具脚本使用了 `ATP_TOKEN_FILE` 或 `ATP_PASSWORD_FILE`，先在当前终端把文件内容读入对应环境变量；验收脚本本身只读取 `ATP_TOKEN` 和 `ATP_PASSWORD`。下面从成功的夹具报告读取项目编号；如由其他流程准备项目，手动给 `$projectId` 赋值。

```powershell
if ($env:ATP_TOKEN_FILE) { $env:ATP_TOKEN = (Get-Content $env:ATP_TOKEN_FILE -Raw).Trim() }
if (-not $env:ATP_TOKEN -and $env:ATP_PASSWORD_FILE) {
  $env:ATP_PASSWORD = (Get-Content $env:ATP_PASSWORD_FILE -Raw).Trim()
}
$projectId = (Get-Content '.local-run/hermes-evaluation-seed.json' -Raw | ConvertFrom-Json).resources.project_id
.\.venv\Scripts\python.exe scripts/hermes-evaluation-acceptance.py `
  --base-url 'http://127.0.0.1:39184/api/v1' `
  --project-id $projectId `
  --report '.local-run/hermes-evaluation-preflight.json'
```

预检通过后，在同一个隔离项目显式执行：

```powershell
.\.venv\Scripts\python.exe scripts/hermes-evaluation-acceptance.py `
  --base-url 'http://127.0.0.1:39184/api/v1' `
  --project-id $projectId `
  --execute --timeout 150 `
  --report '.local-run/hermes-evaluation-result.json'
```

`passed` 表示脚本的结构与确定性评分断言通过；`blocked` 表示项目来源或工具夹具缺失；`failed` 表示模型、工具、路由或评分条件失败。固定十题分别使用独立会话，报告另外列出模型规划挑战题。预检的 `pending_fixture_review` 仅表示题集版本与项目模型绑定字段可用，不表示验收通过。

2026-09-24 已在临时 K3s Backend 复用独立夹具库运行此脚本，修复回答来源范围错误后固定十题 `10 passed`、独立规划挑战 `passed`；详见[当次验收与人工复核](evidence/hermes-k3s-fixed-ten-prompt-v3-2026-09-24.md)。该 Pod 和正式单节点 Release 使用同一修复镜像，但固定题没有在正式业务库项目执行。

固定十题中六道编排题验证确定性规则，两道无结果题验证拒答，仅两道有来源查询题可能调用回答模型。挑战题必须报告 `planner.source=model`、`validation=accepted`、`model_calls=1`，并选出预期的两个只读工具。脚本不把十题的工具选择率解释成模型规划准确率。自动评分只检查路由、状态、证据、模式、引用和必要词，不能判定结论事实是否正确；仍需人工阅读对应 Hermes 会话，核对来源事实、供应商用量与脱敏审计，再记录角色矩阵和异常回退结果。会话不会由脚本自动清理，以便审阅；验收后按隔离环境的数据保留策略处理。
