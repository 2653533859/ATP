# ATP CI/CD 集成指南

## 1. Webhook 触发

ATP 提供通用 Webhook 接口，可在 CI/CD 流水线中触发测试套件或测试计划执行。

### 端点

```
POST /api/v1/webhook/trigger
```

### 认证

通过 `X-API-Key` Header 携带 API Key：

```
X-API-Key: <WEBHOOK_API_KEY>
```

API Key 在后端 `.env` 文件中通过 `WEBHOOK_API_KEY` 配置。

### 请求体

```json
{
  "target_type": "suite",
  "target_id": 1,
  "env_id": null,
  "extra_vars": {}
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `target_type` | string | 是 | `"suite"` 或 `"plan"` |
| `target_id` | int | 是 | 套件 ID 或计划 ID |
| `env_id` | int\|null | 否 | 执行环境 ID |
| `extra_vars` | object | 否 | 额外变量，优先级高于环境变量 |

### 响应

```json
{
  "run_id": 42,
  "target_type": "suite",
  "target_id": 1,
  "status": "pending"
}
```

### cURL 示例

```bash
# 触发套件执行
curl -X POST https://atp.example.com/api/v1/webhook/trigger \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <WEBHOOK_API_KEY>" \
  -d '{"target_type": "suite", "target_id": 1}'

# 触发计划执行，附带额外变量
curl -X POST https://atp.example.com/api/v1/webhook/trigger \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <WEBHOOK_API_KEY>" \
  -d '{"target_type": "plan", "target_id": 3, "extra_vars": {"base_url": "https://staging.example.com"}}'
```

---

## 2. JUnit XML 导出

ATP 支持将执行结果导出为 JUnit XML 格式，供 Jenkins、GitLab CI 等工具解析测试报告。

### 端点

| 端点 | 说明 |
|------|------|
| `GET /api/v1/runs/{id}/junit` | 单用例执行结果 |
| `GET /api/v1/suite-runs/{id}/junit` | 套件执行结果 |
| `GET /api/v1/plan-runs/{id}/junit` | 计划执行结果（包含所有套件） |

> 需要携带 Bearer Token 认证。

### cURL 示例

```bash
# 导出套件执行结果
curl -H "Authorization: Bearer <token>" \
  https://atp.example.com/api/v1/suite-runs/42/junit \
  -o junit-report.xml
```

---

## 3. GitLab CI 集成模板

以下 `.gitlab-ci.yml` 模板展示如何在 GitLab CI 流水线中集成 ATP：

```yaml
stages:
  - test

variables:
  ATP_HOST: "https://atp.example.com"
  ATP_API_KEY: $ATP_WEBHOOK_KEY  # 在 GitLab CI/CD Variables 中配置

api-test:
  stage: test
  image: curlimages/curl:latest
  script:
    # 1. 触发测试套件
    - |
      RESPONSE=$(curl -s -X POST "${ATP_HOST}/api/v1/webhook/trigger" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: ${ATP_API_KEY}" \
        -d "{\"target_type\": \"suite\", \"target_id\": ${ATP_SUITE_ID}}")
      RUN_ID=$(echo $RESPONSE | grep -o '"run_id":[0-9]*' | cut -d: -f2)
      echo "Triggered suite run: $RUN_ID"

    # 2. 轮询等待执行完成（最长 10 分钟）
    - |
      for i in $(seq 1 60); do
        STATUS=$(curl -s -H "Authorization: Bearer ${ATP_TOKEN}" \
          "${ATP_HOST}/api/v1/suite-runs/${RUN_ID}" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
        echo "Attempt $i: status=$STATUS"
        if [ "$STATUS" = "passed" ] || [ "$STATUS" = "failed" ] || [ "$STATUS" = "error" ]; then
          break
        fi
        sleep 10
      done

    # 3. 下载 JUnit XML 报告
    - |
      curl -s -H "Authorization: Bearer ${ATP_TOKEN}" \
        "${ATP_HOST}/api/v1/suite-runs/${RUN_ID}/junit" \
        -o junit-report.xml

    # 4. 检查结果
    - |
      if [ "$STATUS" != "passed" ]; then
        echo "Tests failed with status: $STATUS"
        exit 1
      fi

  artifacts:
    when: always
    reports:
      junit: junit-report.xml
```

### GitLab CI 变量配置

在 GitLab 项目 → Settings → CI/CD → Variables 中添加：

| 变量名 | 说明 |
|--------|------|
| `ATP_WEBHOOK_KEY` | ATP Webhook API Key |
| `ATP_TOKEN` | ATP 用户登录 Token（用于下载报告） |
| `ATP_SUITE_ID` | 要执行的测试套件 ID |

---

## 4. Jenkins 集成

### Pipeline 示例

```groovy
pipeline {
    agent any
    stages {
        stage('API Test') {
            steps {
                script {
                    def response = httpRequest(
                        url: "${ATP_HOST}/api/v1/webhook/trigger",
                        httpMode: 'POST',
                        contentType: 'APPLICATION_JSON',
                        customHeaders: [[name: 'X-API-Key', value: env.ATP_API_KEY]],
                        requestBody: """{"target_type": "suite", "target_id": ${env.ATP_SUITE_ID}}"""
                    )
                    def runId = readJSON(text: response.content).run_id

                    // 轮询等待完成
                    def status = 'pending'
                    for (int i = 0; i < 60; i++) {
                        sleep(10)
                        def check = httpRequest(
                            url: "${ATP_HOST}/api/v1/suite-runs/${runId}",
                            customHeaders: [[name: 'Authorization', value: "Bearer ${env.ATP_TOKEN}"]]
                        )
                        status = readJSON(text: check.content).status
                        if (status in ['passed', 'failed', 'error']) break
                    }

                    // 下载 JUnit 报告
                    httpRequest(
                        url: "${ATP_HOST}/api/v1/suite-runs/${runId}/junit",
                        customHeaders: [[name: 'Authorization', value: "Bearer ${env.ATP_TOKEN}"]],
                        outputFile: 'junit-report.xml'
                    )

                    if (status != 'passed') error("Tests failed: ${status}")
                }
            }
            post {
                always {
                    junit 'junit-report.xml'
                }
            }
        }
    }
}
```
