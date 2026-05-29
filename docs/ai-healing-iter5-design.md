# AI 自愈 iter5 设计

Q8 iter5 的目标是把 AI 自愈从“文本建议”推进到“结构化建议 + 人审应用 + 回归验证”。
第一阶段只落结构化契约和安全白名单，不直接写回用例。

## 结构化建议契约

LLM 必须返回一个 JSON 对象：

```json
{
  "root_cause": "selector changed",
  "confidence": 0.82,
  "patch": {
    "case_type": "web",
    "step_index": 0,
    "action": "click",
    "params": {
      "selector": "button[type=submit]"
    }
  },
  "regression_scope": "single_case",
  "notes": ["review selector before applying"]
}
```

后端通过 `app.services.ai_healing_iter5` 完成：

- prompt 构造：要求只输出 JSON。
- JSON 提取：兼容纯 JSON 和 fenced JSON。
- patch 校验：只允许 Web/Android 低代码步骤。
- preview 应用：生成候选 config，不修改数据库。

## 安全边界

- 默认不允许变更 action。当前阶段只允许更新同 action 的白名单参数。
- 不允许修改 token、password、secret、cookie、authorization 等敏感字段。
- 不允许修改脚本模式、API 请求头、环境变量、项目配置。
- `wait.ms`、`timeout_ms`、`duration` 会被限制在 100-30000ms。
- 文本参数最长 500 字符。

## 白名单字段

Web:

- `click`: `selector`, `timeout_ms`
- `fill`: `selector`, `value`, `timeout_ms`
- `assert_text`: `text`, `timeout_ms`
- `assert_visible`: `selector`, `timeout_ms`
- `wait`: `ms`
- `select`: `selector`, `value`, `timeout_ms`
- `press`: `selector`, `key`, `timeout_ms`
- `hover`: `selector`, `timeout_ms`

Android:

- `click`: `text`, `resourceId`, `resource_id`, `x`, `y`
- `long_click`: `x`, `y`, `duration`
- `swipe`: `direction`, `x1`, `y1`, `x2`, `y2`, `duration`
- `input`: `text`, `value`, `resourceId`, `resource_id`, `clear`
- `press_key`: `key`
- `assert_text`: `text`
- `assert_element`: `resourceId`, `resource_id`
- `wait`: `ms`

## 后续接入

已完成：

- `POST /api/v1/ai-healing/patch-preview`：解析 raw LLM 输出或结构化 suggestion，校验 patch 并返回 preview config。
- 该接口只读，不提交数据库事务；权限要求为工程师及以上，并校验用例所属项目访问权限。
- `POST /api/v1/ai-healing/patch-apply`：应用人工确认的 patch，应用前创建 CaseSnapshot，写审计日志；
  可选触发单用例 regression run，并在 `result_summary` 中记录来源 run/step 与 patch。

后续：

1. 在 `run_diagnosis` 调 LLM 时切换到结构化 prompt，文本建议作为 fallback。
2. 报表展示应用成功率和回归通过率。
3. 前端在执行详情页加入 preview/apply/regression 操作流。
