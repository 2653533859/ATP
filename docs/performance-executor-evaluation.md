# 性能执行器评估（Q17-01 / Q17-02）

## 当前结论

ATP 继续以 k6 作为默认执行器，同时统一接入 Locust 与 gRPC。三种执行器共享项目、环境、节点、取消、资源采样、原始摘要和阈值门禁契约：

| 能力 | k6 | Locust | gRPC |
|------|----|--------|------|
| 脚本 | `.js` / `.mjs` | `.py` | `.proto` |
| 适用协议 | HTTP | HTTP 及自定义 Python 行为 | gRPC Unary / Streaming |
| 可视化编辑 | 支持 | 不支持，手写 Python | 不支持，Proto + options JSON |
| 数据集 | 支持 | 支持 | 通过 request / metadata 占位符使用环境变量 |
| 结果 | k6 summary | Locust aggregate CSV | 统一 RPC 样本摘要 |
| 取消 | 子进程终止 | 子进程终止 | channel 关闭并停止并发槽 |

k6 适合可视化 HTTP 场景和阈值门禁，Locust 适合复杂用户行为，gRPC 适合直接对服务接口做协议级并发验证，JMeter 适合复用 JMX/非 GUI 结果链路。执行器可通过 `GET /api/v1/performance/executors` 查看能力和 ready 状态；worker 通过 `PERFORMANCE_EXECUTORS` 控制实际启用集合，默认值仍为 `k6,locust,grpc`，需要 JMeter 的 Worker 显式加入 `jmeter`。

## gRPC 首版配置

上传 `.proto` 文件后，在压测定义的默认 options JSON 或本次运行覆盖 options JSON 中填写：

```json
{
  "target": "api.example.test:50051",
  "service": "demo.v1.Greeter",
  "method": "SayHello",
  "mode": "unary",
  "request": {"name": "{{ACCOUNT}}"},
  "metadata": {"authorization": "{{API_TOKEN}}"},
  "use_tls": true,
  "timeout_seconds": 30,
  "concurrency": 10,
  "duration_seconds": 60,
  "thresholds": {"p95_ms": ["<500"], "error_rate": ["<0.01"]}
}
```

`mode` 支持 `unary`、`server_stream`、`client_stream` 和 `bidi_stream`。客户端流和双向流可通过 `requests` 数组提供多条请求消息；未提供时使用 `request` 作为单条消息。`iterations` 非空时优先按总 RPC 次数结束，否则按 `duration_seconds` 运行。

Proto 会在 worker 临时目录中编译为 descriptor，不生成或执行用户 Python 代码。service 必须是包含 package 的完整名称，target 必须是 `host:port`，端口范围为 1–65535，单次 RPC 超时不超过 300 秒。

## 安全与运行边界

- 敏感 metadata（authorization、cookie、token、secret、password、API key）只能引用环境变量，不能把密钥写进 options；`*-bin` metadata 必须是 Base64，metadata 不允许换行。
- `target` 同时经过 API 全局 allowlist 和所选节点 Egress allowlist；节点能力必须声明 `grpc` 才能接收指定节点任务。
- TLS 默认使用 worker 的系统信任链；需要 SNI 覆盖时通过 `tls_server_name` 配置。隔离验收环境可使用 `tls_root_certificates_file` 指向 Worker 只读挂载的公有 CA，或使用 `tls_root_certificates` 传入公有 PEM；证书私钥不写入压测定义。
- gRPC 运行只持久化指标与状态计数，不把 request、metadata 或响应正文写入 summary/raw 结果。
- Locust 仍然是可执行 Python，生产部署必须使用专用 worker、最小权限和显式 Egress NetworkPolicy。

## 统一结果

gRPC summary 至少包含 `executor`、`rps`、`p95_ms`、`p99_ms`、`error_rate`、`iterations`、`grpc_statuses`、`grpc_responses`、`exit_code` 和 `thresholds`。RPC 错误按 gRPC status 聚合，成功运行要求至少完成一个 RPC 且无失败；用户主动取消由统一运行状态标记为 `cancelled`，不会伪装成成功摘要。

## 验证证据

`backend/tests/services/test_performance_grpc.py` 启动本地真实 gRPC server，覆盖 Unary、Server Streaming、Client Streaming、Bidirectional Streaming、并发迭代、RPC 失败状态、取消和结果上传；配置校验、API 上传/创建和节点约束另有回归测试。Linux/Kubernetes 外部验收按 [性能 Worker 环境验收 Runbook](performance-environment-acceptance.md) 执行，包含镜像依赖、节点队列、TLS、allowlist、真实 smoke、取消和资源采样证据。
