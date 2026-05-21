# Mock Server 独立端口模式（P1.3 已实现）

> 状态：独立启动器 `backend/app/mock_main.py` + `docker-compose.yml` 中 `mock-standalone` service 已就位（P1.3 Q5 收口）。
> 默认 `MOCK_STANDALONE_PORT=0` 不影响主 backend；启用时主 backend 仍保留 `/mock` 路径，二者并行可行。

## 一、为什么需要独立端口

主 backend 同时承担 REST API、WebSocket、Mock 服务三种职责。当 Mock 流量异常或被压测打高时：

- 主 API 的请求队列被 Mock 请求挤占
- Mock 路径 `/mock/...` 与业务路径 `/api/v1/...` 共享日志与限流配置
- 部分集成方希望使用不带前缀的纯净 URL（如 `http://mock.example.com/3/api/login` 而非 `http://atp/mock/3/api/login`）

## 二、当前能力（主 backend 内嵌模式）

- 路径前缀：`/mock/{project_id}/{path:path}`
- 支持方法：GET / POST / PUT / DELETE / PATCH / HEAD / OPTIONS
- 入口位于 `backend/app/api/v1/mock_server.py`，未与认证中间件耦合
- 缓存命名空间：`atp:mock:{project_id}:*`（与主应用共享 Redis）

## 三、独立端口启动方式

启动器实现位于 `backend/app/mock_main.py`，复用 `mock_server.mock_endpoint`，但暴露**裸路径**：

```python
# 路径模板：/{project_id}/{path:path}
# 例如：POST http://localhost:18000/3/api/login
```

直接进程方式：

```bash
uvicorn app.mock_main:app --host 0.0.0.0 --port 18000 --workers 2
```

Docker Compose（已内置）：

```bash
docker compose --profile mock-standalone up -d mock-standalone
# 验证：
curl http://localhost:18000/health
# {"status":"ok","service":"mock-standalone"}
```

Kubernetes 形态（Helm Chart 当前未内置，复用 backend image 自行 wrap Deployment 即可）：

```yaml
spec:
  containers:
    - name: mock
      image: registry.local/atp/backend:1.0.0
      command: ["uvicorn", "app.mock_main:app", "--host", "0.0.0.0", "--port", "18000"]
```

## 四、与主应用的状态同步

由于规则/快照仍写入同一 PostgreSQL，独立 Mock 进程立即可见 backend 写入的规则变更；缓存失效通过共享 Redis 完成（`invalidate_mock_cache` 写 `atp:mock:*:*` pattern delete）。

## 五、不同模式对比

| 维度 | 主 backend 内嵌 | 独立端口 |
|------|----------------|---------|
| URL 前缀 | `/mock/{pid}/{path}` | `/{pid}/{path}` |
| 进程隔离 | 与 REST API 共享 | 独立进程，可单独扩缩 |
| 中间件 | 含 CORS / CSRF / rate_limit | 仅 OTel，无 auth/CORS |
| OTel service.name | `atp-backend` | `atp-mock` |
| 端口 | 8000 | 18000（可改 `MOCK_STANDALONE_PORT`） |
| 启用方式 | 默认 | `--profile mock-standalone` |

## 六、相关代码

- `backend/app/mock_main.py` — 独立启动器（P1.3 新增）
- `backend/app/api/v1/mock_server.py` — 共享的 mock 路由实现
- `backend/app/api/v1/mock_rules.py` — 规则 CRUD + 版本快照 + 录制转正式
- `backend/app/models/mock.py` — `MockRule` 模型
- `backend/app/models/mock_snapshot.py` — `MockRuleSnapshot` 模型
- `backend/app/core/config.py` — `MOCK_STANDALONE_PORT` 配置项
- `docker-compose.yml` 中 `mock-standalone` service（profile=`mock-standalone`）

