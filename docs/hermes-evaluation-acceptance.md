# Hermes 固定题与模型规划验收

`scripts/hermes-evaluation-acceptance.py` 对显式指定的项目运行 `hermes-core-v2` 固定题，并额外运行一道确定性路由不会命中的模型规划挑战题。默认只读取评测集和项目元数据；传入 `--execute` 才提交问题。脚本不创建、修改或删除业务资产，但执行模式会创建 Hermes 会话、审计记录，并可能调用收费模型。报告只保留题号、模式、工具状态、结果和原因码，不保存回答、来源正文、令牌或密码。

## 环境前置

1. 使用独立数据库和专用项目，通过正常 API/业务流程准备可访问的 `case` 运行编号 1、需求编号 1、知识编号 1、需求—用例关联、近期失败任务与质量趋势，以及匹配“登录”的项目来源。不要在现有业务库强行改写主键。
2. 项目绑定已启用的模型配置；验收账号具有项目 viewer 权限。预检只能确认绑定字段，不能证明模型可用或夹具齐全。
3. Backend 部署当前题集版本 `2026-09-23.1`。旧 Backend 会被版本门禁拦下。发布机在 2026-09-23 的只读核对仍为 `bdb84286`，尚未部署本契约。
4. 使用独立账号或短期令牌，并核对已发布的全局知识不会误充当前项目的预期来源。

## 运行

在 Windows 工作区，先把短期令牌放在当前终端环境变量中；也可改用 `ATP_USERNAME` 与 `ATP_PASSWORD`。不要把认证值放在命令行、报告路径或仓库中。

```powershell
$env:ATP_TOKEN = '<short-lived-token>'
.\.venv\Scripts\python.exe scripts/hermes-evaluation-acceptance.py `
  --base-url 'http://127.0.0.1:39083/api/v1' `
  --project-id <isolated-project-id> `
  --report '.local-run/hermes-evaluation-preflight.json'
```

预检通过后，在同一个隔离项目显式执行：

```powershell
.\.venv\Scripts\python.exe scripts/hermes-evaluation-acceptance.py `
  --base-url 'http://127.0.0.1:39083/api/v1' `
  --project-id <isolated-project-id> `
  --execute --timeout 150 `
  --report '.local-run/hermes-evaluation-result.json'
```

`passed` 表示脚本的结构与确定性评分断言通过；`blocked` 表示项目来源或工具夹具缺失；`failed` 表示模型、工具、路由或评分条件失败。固定十题分别使用独立会话，报告另外列出模型规划挑战题。预检的 `pending_fixture_review` 仅表示题集版本与项目模型绑定字段可用，不表示验收通过。

固定十题中六道编排题验证确定性规则，两道无结果题验证拒答，仅两道有来源查询题可能调用回答模型。挑战题必须报告 `planner.source=model`、`validation=accepted`、`model_calls=1`，并选出预期的两个只读工具。脚本不把十题的工具选择率解释成模型规划准确率。自动评分只检查路由、状态、证据、模式、引用和必要词，不能判定结论事实是否正确；仍需人工阅读对应 Hermes 会话，核对来源事实、供应商用量与脱敏审计，再记录角色矩阵和异常回退结果。会话不会由脚本自动清理，以便审阅；验收后按隔离环境的数据保留策略处理。
