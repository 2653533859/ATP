# Q18 最新开发状态与前后实现对比

## 2026-08-24 N6.7 q19 独立 Web 录制 Worker 持久部署与真实录制验收

- q19 Compose 已新增独立 `web-recorder` 服务，Backend 固定为 Worker 模式，录制服务使用同一 Redis 路由前缀、Xvfb `:99`、启动锁清理、socket 就绪等待和 `init: true` 子进程回收。
- 本地 API/传输/smoke/部署契约回归 `61 passed`；代码审查发现并修复 Xvfb 重启残留锁和 Chromium 僵尸进程问题，Ruff 与 `git diff --check` 通过。
- q19 真实临时项目完成 Chromium 录制、2 步快照、PNG 截图、停止、删除和 Worker 重启恢复；Backend `/health`、Prometheus targets 正常，Worker `active_sessions=0`、容器僵尸进程数为 `0`。
- 脱敏证据见 [`q19-web-recorder-readiness-2026-08-24.json`](evidence/q19-web-recorder-readiness-2026-08-24.json)、[`q19-web-recorder-restart-readiness-2026-08-24.json`](evidence/q19-web-recorder-restart-readiness-2026-08-24.json) 与 [`q19-web-recorder-init-readiness-2026-08-24.json`](evidence/q19-web-recorder-init-readiness-2026-08-24.json)。Trace/HAR/Console/网络日志/运行报告完整链路、Firefox/WebKit、Android、真实性能节点、通知和外部缺陷平台仍待验收。

## 2026-08-24 N6.6 q19 持久通用 Web Worker 部署与恢复验收

- q19 使用提交 `f1473d2` 重建并持久启动独立 `worker` 服务，监听 `default,maintenance`；性能 Worker 保持 `performance.worker-a,performance`，Celery ping、队列隔离和 Prometheus targets 均通过。
- Web 低代码下载首次执行 `run 4`、Worker 重启后的 `run 5` 均通过并回传 1 个下载对象，临时项目和对象清理通过；脱敏证据见 [`q19-persistent-web-worker-readiness-2026-08-24.json`](evidence/q19-persistent-web-worker-readiness-2026-08-24.json)、[`windows-persistent-web-worker-readiness-2026-08-24.json`](evidence/windows-persistent-web-worker-readiness-2026-08-24.json) 与 [`windows-persistent-web-worker-restart-readiness-2026-08-24.json`](evidence/windows-persistent-web-worker-restart-readiness-2026-08-24.json)。
- 当前独立录制 Worker、Android 真机、真实性能节点、通知和外部缺陷平台仍待验收；下一步优先补独立录制 Worker 的 q19 持久部署和 Trace/报告链路。

## 2026-08-24 N6.5 q19 真实迁移与 Web Worker 临时验收

- 最新 `main`（提交 `5179826`）已部署到 q19 验收栈，目标数据库从 `20260814_0059` 真实升级到 `20260824_0065`；Backend、PostgreSQL、Redis、MinIO、性能 Worker 和 Beat 健康，Backend `/health` 返回 HTTP 200。
- 通过项目 API 创建/删除临时项目，HTTP `204` 且项目、环境和模块残留均为 `0`；启动临时默认队列 Worker 完成 Web 低代码下载执行 `run 3`，下载对象和清理通过，验收后移除临时 Worker。
- 脱敏证据见 [`q19-migration-web-worker-readiness-2026-08-24.json`](evidence/q19-migration-web-worker-readiness-2026-08-24.json) 与 [`windows-web-worker-readiness-2026-08-24.json`](evidence/windows-web-worker-readiness-2026-08-24.json)。当前 q19 持久编排尚未加入通用 Web Worker；Android 因 ADB offline 未执行，真实性能节点、通知和外部缺陷平台仍待验收。

## 2026-08-24 N6.4 Windows 完整 API/Web 验收与项目删除级联修复

- Windows 完整 smoke 已通过管理员登录、认证读接口、远端 PostgreSQL/Redis/MinIO readiness、Web Recording 状态、Playwright `12 passed`、Chromium/Firefox/WebKit 矩阵、文件上传/清理和 HTML/JUnit 报告导出；脱敏证据见 [`windows-full-readiness-2026-08-24.json`](evidence/windows-full-readiness-2026-08-24.json)，必需失败数为 `0`。Web 低代码真实执行和 Android 相关检查因未指定用例/未启用 Worker 保持 optional skip。
- 清理验收夹具时发现项目删除会被 `environments_project_id_fkey` 阻断；已补充 Alembic `20260824_0065`，并同步模型上的 APK、环境、模块、计划、套件项目级级联，环境变量级联删除和计划环境引用 `SET NULL`。项目路由、新迁移契约、迁移目录和 Ruff 定向回归通过；远端 q19 临时项目已清理。
- 当前下一步是补独立录制 Worker 的 q19 持久编排与真实录制/Trace/报告链路，再继续 Android Worker/真机、真实性能节点、通知渠道和外部缺陷平台验收。严格 readiness 仍因当前 Windows 缺少 Docker Compose 工具保持明确阻塞，不将其伪装为通过。

## 2026-08-24 N6.3 Windows 发布 readiness 与远端依赖恢复

- 复核 `172.31.27.133` 时发现旧 Redis 容器的网络与 6379 发布状态不一致，清理异常容器元数据并保留挂载数据目录；重启 Docker 网络层后，Redis 6379、PostgreSQL 5432、MinIO 9000 从 Windows 可达，q19 验收栈依赖链的 Backend `/health` 返回 HTTP 200，其他 Worker/目标服务仍需单独复核。
- Windows 最小 smoke 通过 doctor、后端健康、前端登录页、三项远端依赖、ADB 可执行文件、k6/Locust/gRPC 和性能队列检查，证据见 [`windows-release-readiness-2026-08-24.json`](evidence/windows-release-readiness-2026-08-24.json)。报告中的 Android 设备为 warning，未把无真机状态计为通过。
- 本轮命令显式跳过管理员登录、认证读接口、Playwright/浏览器矩阵、文件上传、报告导出和 Android 用例；本机 readiness 默认仓库检查通过，严格模式因 Windows 缺少 Docker Compose 工具而失败。该记录只覆盖 API/Web 最小链路和远端依赖恢复，完整发布及 Android/Worker、性能、通知、外部缺陷平台仍 pending。

## 2026-08-24 N6.2 导航、配置中心与发布文档状态

- 当前产品导航已固定为“工作台、测试能力、测试资产、智能中枢、系统”五组；旧 URL、旧 API 和领域页面保持兼容。配置中心入口为 `/system/config`，远程工具箱入口为 `/system/toolbox`。
- 配置中心已完成本地实现和自动化回归：管理员可查看脱敏配置、版本差异和影响提示，并通过精确 `ROLLBACK` 回退单个资源；普通测试角色访问会被权限守卫拦截。该证据不代表真实数据库、生产密钥或外部依赖已验收。
- N6.1 浏览器回归定向 `2 passed`、全量 Playwright `12 passed`，前端 Vitest `65 files / 258 tests passed`，type-check 和生产构建通过。下一步是 N6.2 的真实环境证据、发布 readiness 和外部依赖验收。

## 2026-08-12 iOS/Appium 验收入口

- 新增 `scripts/ios-appium-acceptance.py`，支持 Appium readiness、显式 W3C/XCUITest session、受控 iOS 步骤、截图、可选录屏/syslog 和脱敏 JSON 报告。
- 本地协议/安全回归已通过；status-only 不代表真实设备通过，macOS/Xcode/WDA/iPhone/Simulator、设备租约和 ATP `ios` 队列仍保持 pending。

## 2026-08-12 Web 专用 Worker 健康探针

- 独立 Web 录制 Worker 在 Redis 注册/心跳成功后更新 `WEB_RECORDER_HEALTH_FILE`，停止时清理；Compose 和 Helm 已增加 readiness/liveness 探针。
- 本地 Worker/部署契约回归已通过；Docker 容器、Linux/Xvfb、Firefox/WebKit、Trace/网络日志和跨副本 E2E 仍保持环境验收状态。
- 浏览器矩阵 smoke 已支持显式 artifact 目录，按浏览器生成 Trace/HAR 及 Console、失败请求、HTTP 错误摘要；无 artifact 配置时保持原有轻量输出。
- Windows 本机三浏览器矩阵真实通过：Chromium、Firefox、WebKit 均返回 200、登录页输入框数量为 4，失败请求和错误响应为空；汇总证据见 `docs/evidence/web-browser-matrix-local-smoke-2026-08-12.json`。

## 2026-08-12 Linux/Kubernetes Prometheus 验收入口

- `scripts/performance-environment-smoke.py` 新增 `--prometheus-url`/`--prometheus-query`，会验证 Prometheus readiness、PromQL API 成功状态和结果数组，并将结果纳入脱敏验收报告。
- 定向脚本回归已通过；真实 Linux/Kubernetes 集群、生产 Prometheus 和外部目标服务仍保持 pending，不以 Windows 本地 Prometheus 结果替代。

## 2026-08-12 Windows Prometheus 目标指标与性能 UI

- 性能定义编辑器已提供目标服务指标配置：可选择 Prometheus 直连 URL 或环境变量，设置查询超时并维护多条 PromQL；保存前会校验来源和查询，配置写入 `default_options.target_metrics`。
- 压测详情支持按来源查看资源指标，区分 Worker 资源与 `target-service-prometheus` 样本，并动态展示目标查询返回的指标名。
- 本机 Prometheus v3.13.1 已通过 readiness 和 Backend `/metrics` 抓取检查；带目标指标的 k6 run `11` 成功，20 次迭代、错误率 0、6 条采样（其中 3 条目标服务样本），证据见 [`performance-windows-local-prometheus-target-metrics-2026-08-12.json`](evidence/performance-windows-local-prometheus-target-metrics-2026-08-12.json)。
- 前端定向 `PerformanceCenterView` 回归 `5 passed`，全量 `44 files / 180 tests passed`，type-check/build 通过。真实外部目标、Linux/Kubernetes Prometheus、生产 SLO 历史、通知和 Android 设备仍保持 pending；Linux MCP 当前传输层关闭。
- 完整非集成后端回归 `1899 passed`，259 个测试文件独立扫描 `259 passed, 0 failed`；这证明本地测试隔离和代码回归稳定，不代表真实 Linux/Kubernetes 或设备环境已验收。
- Windows 冒烟新增 `-EnvFile`，解决实际运行档案与根 `.env` 不一致时 Redis/MinIO doctor 误报的问题；使用当前 `remote-infra.env` 重跑，10 项 Playwright、Chromium/Firefox/WebKit 矩阵、Web 下载对象闭环和清理均通过，证据见 [`windows-local-smoke-remote-infra-web-seed-2026-08-12.json`](evidence/windows-local-smoke-remote-infra-web-seed-2026-08-12.json)。
- 未传参数时会根据 `windows-local-runtime.json` 自动使用当前运行档案；轻量 smoke 已验证该默认选择路径。

## 2026-08-12 当前工作区核对与配置安全收口

- 根目录 `.env` 的 Windows `local-all` 当前使用 `172.31.27.133`；独立的被忽略性能 Agent 配置仍是另一套历史验收环境，不能混用其凭据或运行证据。
- 启动配置远端档案不再预置特定环境的 PostgreSQL/MinIO 用户名；`<server-host>`、`<database-user>`、`<minio-user>` 和示例密钥会被必填检查识别为未完成。
- `docs/external-infra-run.md` 已移除公网地址、管理员账号和明文密码，改为 `.env`/启动档案占位符说明。
- 当前前端全量回归为 `44 files / 180 tests passed`，`vue-tsc --noEmit`、Vite 构建和 Windows doctor 均通过；k6/Locust 已在 Windows 本机 ATP `/health` 目标完成真实平台执行，Android 真机及 Linux MCP 外部验收仍保持 pending。
- 补充运行态：Locust `2.32.10` 已安装并通过 Windows doctor；由于 `172.31.27.133:5432` 当前握手超时，本机服务暂用已验收的 `remote-infra.env`（163.192.40.209）运行，根目录 `.env` 未修改，不能把当前运行证据归属到 172 主机。
- Windows 本地性能证据：k6 测试 `7` / run `8` 成功（20 次迭代、错误率 0、3 条资源指标），Locust 测试 `8` / run `10` 成功（168 次请求、错误率 0）；详见 [`k6 smoke`](evidence/performance-windows-local-k6-smoke-2026-08-12.json) 与 [`Locust smoke`](evidence/performance-windows-local-locust-smoke-2026-08-12.json)。
- Windows `status` 已增加脱敏运行元数据，直接显示实际生效档案、基础设施地址和队列；`down` 会清理元数据。

## Worker 测试外部依赖隔离修复（2026-08-12）

- 修复 Worker 测试未隔离真实 Redis 取消控制客户端的问题；Worker `427 passed`，完整非集成后端 `1889 passed`，覆盖率 `82.13%`。
- SSH/MCP 会话当前仍无法恢复，真实 k6、metrics、Kubernetes/Prometheus 和 Android 外部验收保持 pending。

## 2026-08-12 Linux 性能验收栈与验收工具修复

- Windows 性能验收 bundle 已生成并以 POSIX ZIP 路径部署到 `172.31.27.133:/opt/atp-q17-acceptance`；远端性能 Worker 镜像包含 k6、Locust、gRPC、JMeter 和 Chromium/Firefox/WebKit，Compose 隔离栈已启动。
- API/节点 smoke 已证明 Backend 健康、四类执行器 ready、`worker-a` online、队列及目标 allowlist 正确，证据保存在远端 `docs/evidence/performance-api-node-2026-08-12.json`。
- 验收脚本补充了报告 `Path` 转字符串和 state-changing 请求 `X-Requested-With`；本地脚本回归 `17 passed`。真实压测 run/metrics 仍待远端工具镜像重跑，完整外部验收保持 pending。

## 2026-08-12 Windows 性能验收 bundle

- 新增 `scripts/package-performance-acceptance.ps1`，按 allowlist 收集性能 Compose、Backend/Worker 构建上下文、验收夹具、工具和 Runbook，排除真实配置、虚拟环境、缓存和本地运行产物。
- bundle 内置逐文件 SHA-256 清单，压缩包旁生成校验文件；本机实测 323 个文件、校验一致且无密钥/证书条目，`worktree_dirty` 会如实标记未提交改动。
- 这一步只完成安全、可审计的传输准备，目标 Linux/Kubernetes 的镜像构建、节点心跳和真实 smoke 仍待外部环境。

## 2026-08-12 Web 录制浏览器选择

- Web 录制 API 与 `WebRecorderModal` 现在支持 Chromium、Firefox、WebKit 三种 Playwright 浏览器，启动时显式选择，默认使用 Chromium；录制进行中锁定选择。
- 录制会话快照会返回实际使用的浏览器，跨 Worker 查询和停止录制后仍可追溯配置。
- 界面会提示所选浏览器必须安装在 Worker 镜像中，缺少浏览器时保留明确错误，不做隐式回退。
- 本轮验证：Web 录制 API/传输层定向 `33 passed`；完整非集成后端 `1886 passed`、Python 3.12 覆盖率 `82.13%` 且门禁通过；前端全量 `44 files / 177 tests passed`，覆盖率 statements/branches/functions/lines 为 `36.25% / 31.37% / 28.58% / 37.83%`，type-check/build 通过。

## 2026-08-12 Windows Worker 模式隔离补充

- `windows-local.ps1` 的普通 Worker 进程识别排除 `--hostname android-win-*` 和 `--hostname performance-win-*`，不会把专用 Android/性能 Worker 当成普通 Worker 管理。
- `windows-local.ps1` 与 `windows-android-worker.ps1` 现在双向检查 `android`/`mobile_special` 队列冲突：`local-all` 和 `android-agent` 不能在同一台 Windows 主机同时启动；冲突会在停止现有服务前明确失败并提示切换启动档案。
- 当前 Windows `local-all` 已恢复运行，反向启动 Android Agent 的冲突保护已用真实运行中的普通 Worker 验证；Windows 合约测试 `5 passed`，两个 PowerShell 脚本解析通过。ADB 当前无设备，真实 Android 扫描/执行仍待设备环境。

## 2026-08-12 Linux 目标主机只读审计

- 已对配置的 Linux 主机做只读探测：主机具备 Docker/Compose，运行 PostgreSQL、Redis、MinIO，但现有 `/opt/testhub_platform` 是独立 Django 项目，ATP 的 `/health` 和 `/api/v1/health` 均不存在；当前 `8001` 服务不能作为 ATP 验收后端。
- 未发现 ATP 的 Q17 性能隔离验收栈或 Prometheus；本次没有停止、重启、部署或修改远端任何服务。Q17-04、真实性能节点和外部目标服务仍需单独准备隔离环境。

## 2026-08-12 性能验收启动竞态修复

- Compose 性能验收栈新增 Backend `/health` healthcheck，性能 Worker 与验收工具等待 Backend `service_healthy` 后再运行。
- 验收脚本新增 `--node-ready-timeout-seconds`，默认等待 60 秒的专用 Worker 心跳；节点在线后才继续校验队列、能力、目标 allowlist 和真实运行，新增离线→在线回归覆盖该路径。
- 定向性能部署/验收回归 `27 passed`，真实镜像、TLS 目标和资源采样仍需目标环境留证。

## 2026-08-12 Windows 部署 readiness 修复

- `validate-deployment-readiness.py` 已兼容 Windows 本地代码页下的 shell 输出，避免 UTF-8/非 UTF-8 混合输出导致 readiness 命令崩溃；空 stdout/stderr 也会安全归一。
- 当前命令实际通过仓库部署检查，Docker/Helm 缺失被明确记录为 SKIP；部署文档回归 `13 passed`。这只完成本地工具可靠性，不替代 Linux/Kubernetes 发布验收。

## 2026-08-12 Web 录制 Worker 并发路由补强

- API 录制会话创建在候选 Worker 明确返回 `busy/not_ready` 时会切换到下一个有容量 Worker；超时和未知错误不重试，避免响应丢失时重复创建浏览器会话。
- `backend/tests/services/test_web_recording_transport.py` 新增多 Worker fallback、超时不重试和启动响应异常清理回归，录制传输层测试为 `13 passed`；真实跨副本 Worker、Xvfb 和浏览器矩阵仍需环境验收。
- Worker 启动成功但返回无效快照时，API 会主动发送停止命令清理可能已创建的浏览器会话，避免残留会话占满 Worker 容量。
- `WebRecorderModal` 停止录制失败时不再自动导入步骤或关闭弹窗；组件回归覆盖 `autoApply` 失败路径。

## 2026-08-12 API gRPC 流式调用

- API gRPC 执行器已根据 Proto 方法描述自动选择 Unary、Server Streaming、Client Streaming 和 Bidi Streaming；Client/Bidi 请求使用非空 JSON 数组，响应统一进入 body、提取和断言契约。
- 用例编辑器补充请求格式提示；新增三种流式模式和多文件 Proto 回归，相关 gRPC 执行器测试 `68 passed`，完整非集成后端更新为 `1886 passed`、Python 3.12 覆盖率 `82.13%`，前端 `44 files / 177 tests passed`，type-check/build 通过。
- 当前仍需真实 Unary/Streaming 目标服务联调，因此能力矩阵标记为“待环境验收”。

## 2026-08-12 gRPC Proto 文件读取

- gRPC 用例编辑器新增主 `.proto` 与 import 文件读取按钮，内容直接回填/保存为配置，不走对象存储上传；Worker 会安全重建 import 目录。
- 新增 `frontend/src/utils/grpcProtoFile.spec.ts`，文件读取与边界校验 `5 passed`；前端全量 `44 files / 177 tests passed`，type-check/build 通过；真实服务/TLS 联调状态不变。

## 2026-08-12 Windows 冒烟 CSRF/会话修复

- 修复 Windows 冒烟文件上传的 CSRF 403 和手工 Cookie 401：写请求统一带 `X-Requested-With`，上传使用 `CookieContainer` 复用登录会话。
- 修复后真实冒烟通过 10 项 Playwright、Chromium/Firefox/WebKit 矩阵、管理员登录、文件上传和临时 MinIO 对象清理；报告为 `.local-run/windows-smoke-20260812-003248.json`。
- 自包含 Web 下载 seed 随后通过：临时项目 9、用例 5 审核/执行成功，1 个下载对象写入，清理删除项目、1 个环境和 5 个运行产物；报告为 `.local-run/windows-smoke-20260812-003448.json`。

## 2026-08-12 Windows 性能节点队列与配置同步

- Windows 本地 Worker 现在允许 `performance.worker-a` 这类专用队列，并在显式启用性能节点时自动监听共享 `performance` 队列和节点队列。
- 页面注册的节点标记为 UI 管理，Worker 心跳不会再用 `.env` 默认值覆盖页面保存的容量、出口和执行器配置；队列不一致时保持离线并记录错误。环境变量自动创建的节点仍由 Worker 配置管理。
- 相关后端定向回归 `82 passed`；当前完整非集成后端 `1871 passed`、Python 3.12 覆盖率 `82.08%`，前端 `42 files / 170 tests passed`，type-check/build 通过。

## 2026-08-12 性能节点诊断展示补充

- 性能节点页面新增 `last_error` 诊断展示，队列不匹配时可直接看到 Worker 与节点配置的具体差异原因。
- 新增前端回归测试；当前前端全量为 `42 files / 170 tests passed`，`vue-tsc --noEmit` 和生产构建通过。

## 2026-08-11 性能中心 JMeter 配置入口

- 性能中心执行器切换已补齐 JMeter，选择后自动进入脚本模式，并依据后端能力使用 `.jmx` 上传限制；此前后端能力已存在，但前端切换处理会拒绝 JMeter。
- 新增组件回归覆盖 JMeter 切换、脚本模式和 `.jmx` 接受类型；前端全量 `42 files / 169 tests passed`，type-check/build 通过。

## 2026-08-11 性能压测节点注册与配置

- 性能中心新增节点注册/编辑/删除入口，可配置节点 ID、队列、启用状态、执行器能力、最大 VU、最大并发和目标出口 allowlist；节点卡片与运行节点选择会展示执行器能力。
- 页面复用现有性能节点 API，写操作由工程师权限保护；Worker 心跳、在线状态和实际容量校验仍由后端/Worker 负责，尚未把页面保存误认为节点已在线。
- 新增节点表单 payload、allowlist 去重和校验回归；前端全量 `42 files / 169 tests passed`，type-check/build 通过。

## 2026-08-11 项目归档只读边界补充

- 归档项目现在不仅阻止测试资源写入/执行，也阻止项目自身配置编辑；API 依赖和项目列表按钮均已收口，恢复后才可修改。
- 项目后端权限/路由回归 `36 passed`，项目列表前端回归 `4 passed`；`vue-tsc` 和生产构建通过。

## 2026-08-11 Windows Web 低代码冒烟同步

- Windows 冒烟新增 `-WebCaseId`、`-RequireWebLowcode`、`-RequireWebDownload` 和超时配置，可用管理员 Cookie 触发已有 Web 低代码用例、轮询 `/runs/{run_id}`，并按需强制验证 download 步骤的对象引用。
- 新增显式 `-SeedWebDownloadCase` 自包含模式：按需创建临时项目/模块/用例，自动提交审核并批准后执行网络守卫允许的内联 `data:` 下载夹具，终态后自动删除；超时或未知状态会保留资源并提示手工清理。不传用例 ID/seed 开关时不改变原有冒烟流程。
- 启动档案入口和底层 `-EnvFile` 现在都会把选中的配置临时注入新启动的子进程，并在启动后恢复当前 PowerShell 会话；缺少选中档案时直接失败，不再静默使用默认连接配置。
- Android Agent `up/restart` 已增加启动前 doctor 门禁；基础服务、Python/Celery 或 ADB 不通过会阻止启动，未连接设备仍保持 warning 级别。
- 首次环境没有历史运行记录时，seed 模式需要配合 `-SkipReports`；当前 Windows 已用真实 Worker/MinIO 完成下载对象写入、读取和清理验证。该证据限定于当前 Windows 环境，不外推 Linux、容器或真实设备验收。
- PowerShell 解析和 Windows 合约回归 `4 passed`。

## 2026-08-11 Windows Web 下载夹具同步

- 仓库内置本地下载页面 `frontend/public/atp-windows-download.html` 和配套文本文件，Web 低代码用例可直接引用 `#atp-download-link`。
- Playwright 已验证下载事件和文件名；聚焦 seed 冒烟最近一次在当前 Windows 环境完成真实低代码运行、Worker/MinIO 对象写入和终态清理，临时项目 8/用例 4/运行 4 通过并删除 1 个环境和 5 个运行产物；已有用例复用模式仍可使用 `-WebCaseId -RequireWebDownload`。

## 2026-08-11 三方 OpenAI 兼容模型配置同步

- AI 模型配置新增 `openai_compatible` 协议，适用于 Open WebUI、One-API、LiteLLM 等提供 OpenAI-compatible `/v1` 的第三方服务。
- Endpoint 必填；模型发现使用 `{Endpoint}/models`，实际生成使用 `{Endpoint}/chat/completions`，API Key 继续加密保存且不回传。
- 配置页已新增协议选项、Endpoint 说明和模型拉取入口；真实 Token、模型列表、多模态和思考参数仍需目标服务验收。
- 定向回归 `31 passed`，前端 AI 配置组件回归 `2 passed`；当前全量后端 `1871 passed`、Python 3.12 覆盖率 `82.08%`，前端 `42 files / 169 tests passed`、coverage `33.13% / 28.49% / 25.73% / 34.52%`，type-check/build 通过。

## 2026-08-11 Mock 规则 AI 生成同步

- Mock 页面新增独立“AI 生成 Mock”入口，支持自然语言要求和可选参考规则；原有“AI 生成用例”入口保持不变。
- 生成结果先进入可编辑 JSON 预览，确认后才复用普通创建接口保存；服务端不直接落库，并校验项目权限、AI 配置和参考规则归属。
- 定向回归：后端 Mock AI 服务/API `9 passed`、前端 Mock 页面 `5 passed`；type-check、Ruff check/format 已通过。

## 2026-08-11 Web 录制 Worker 服务化同步

- 已完成 Redis 心跳/容量选择/命令回复/会话路由控制面，以及独立入口 `python -m app.web_recording_worker`；API 在 `WEB_RECORDER_MODE=worker` 时通过 Redis 路由会话，默认 `local` 模式和 Windows 本地录制保持兼容。
- Windows `local-dev.cmd` 会按配置自动托管 Web Recording Worker；Compose `web-recorder` profile、Helm `webRecorder` Deployment 和启动配置 UI 已同步，Linux Worker 使用 Xvfb/`WEB_RECORDER_DISPLAY`。
- Windows 启动前诊断已进一步校验 Web 录制模式、Python Playwright/Chromium、Worker 队列与并发参数；Android Agent doctor 已增加 Celery/Redis Python 依赖检查。当前机器 `local-dev.cmd doctor` 通过，仅有 Android 设备未连接的可选警告；k6/Locust 已完成本机真实平台执行。
- Android 设备扫描在 `ADB_SCAN_MODE=worker` 时已补充任务 ID 和状态轮询，设备页会等待 Windows Worker 写回真实 ADB 结果后再提示完成；本地 `local` 模式保持同步扫描。
- Windows Android Worker 已补充 Redis TTL 注册与心跳，设备页新增在线 Agent 状态；脚本自动注入 `ANDROID_WORKER_ID`，普通 Worker 不会被误识别。
- Windows 全量冒烟在 Android Worker 模式下会校验在线注册并轮询设备扫描回调，避免只验证网络连通而漏掉队列链路。
- 本轮回归覆盖 API 远程分支、Worker 生命周期/容量、Redis 路由、部署契约、Android Agent 扫描状态和 Worker 在线注册，以及数据集/Mock 页面 AI 生成草稿、三方模型协议、性能中心 JMeter 入口、性能节点注册配置和 Windows 队列同步；后端非集成 `1871 passed`、Python 3.12 覆盖率 `82.08%`、256 个测试文件单独运行通过，前端 `42 files / 169 tests passed`、coverage `33.13% / 28.49% / 25.73% / 34.52%`、type-check/build 通过；真实 Linux/Xvfb、Firefox/WebKit、JMeter Worker、性能节点心跳/消费以及跨 API 副本 E2E 仍待目标环境验收。

更新时间：2026-08-12

本文件是 `docs/implementation-plan-2026-Q18-capability-expansion.md` 的最新查看入口，配合 `docs/capability-baseline-2026-08-07.md` 使用。状态区分为：

- **已实现**：代码、调用入口和自动化回归已具备。
- **部分实现**：主链已具备，但仍缺少真实设备、外部服务或更完整的工程化验收。
- **外部阻塞**：需要当前 Windows 开发环境之外的资源，不能用本地模拟结果代替。

本次同步（2026-08-12）：Windows 主线新增 API/GraphQL OAuth2 Client Credentials 与 Digest 认证配置、执行器接线、token 缓存和回归测试；Web 低代码执行器与录制器新增逐请求浏览器网络守卫，覆盖重定向、DNS 变化和子资源内网 egress；数据集管理页新增 AI 生成合成数据入口，生成结果先回填编辑器并沿用校验/版本保存流程；全量冒烟已实测通过真实健康检查、管理员登录、认证读接口、Playwright 10 项、Chromium/Firefox/WebKit 页面矩阵、临时文件上传/清理、HTML/JUnit 报告生成和可选停止服务，并生成脱敏 JSON 报告；Windows Web 低代码 seed 已进一步完成真实 Worker/MinIO 下载对象写入、读取和清理；Windows 本地 k6/Locust 与 Prometheus 目标指标关联也已完成真实闭环，当前开发重点转为 Android 扫描/真实设备，以及 Linux/Kubernetes、生产 Prometheus/SLO 历史、专用浏览器 Worker、外部通知和真实 Provider/Consumer/OAuth2/Digest 服务验收。

## Windows 主线与目标环境分层

| 范围 | 当前状态 | 下一步 |
|---|---|---|
| Windows 日常开发 | Windows 本地启动、远端 PostgreSQL/Redis/MinIO、PowerShell 进程托管、Playwright、ADB、`local-dev.cmd doctor`、性能依赖检测、Windows Prometheus 本地目标指标采样和全量本地冒烟已具备；本次冒烟真实通过健康/登录/认证读接口、Playwright 10 项、Chromium/Firefox/WebKit 页面矩阵、临时文件上传/清理、HTML/JUnit 报告生成和可选停止服务；Web 下载 seed 已完成真实 Worker/MinIO 留证并自动清理 | 复用已有用例做 `-WebCaseId` 运行留证，并准备 Android 设备 |
| Linux/Kubernetes 目标环境 | 性能 Worker、节点队列、TLS、allowlist、资源采样和验收工具已实现 | 完成真实镜像、真实目标服务、取消、Prometheus 和证据归档 |
| macOS/iOS 目标环境 | iOS/Appium W3C 执行边界、资产、租约和专用队列已实现 | 准备 macOS/Xcode/WDA/签名 IPA/设备并完成最小闭环 |
| 真实 Android 设备池 | Android 租约、矩阵、录屏、日志和系统动作已实现 | 准备设备池并完成并发、权限、旋转、网络和系统事件验收 |

Windows 端的完善项属于本地开发体验和联调效率，不要求在 Windows 上模拟 Linux/Kubernetes 生产性能；生产级多进程性能和专用 Worker 仍转移到目标环境验收。

## 前后实现对比

| 能力域 | 之前 | 现在 | 状态与验证入口 |
|---|---|---|---|
| API 断言与 Schema 资产 | 只有基础状态码、字段、Schema 等断言，复杂表达式和 Schema 复用边界不清晰 | 增加 AST 白名单解释器、项目级 JSON Schema 资产 CRUD/版本，以及执行时项目隔离解析 | 已实现；`backend/app/services/safe_expressions.py`、`backend/app/api/v1/api_schema_assets.py` |
| API 高级认证 | 仅支持 Bearer、Basic、API Key，OAuth2/Digest 需要手工脚本或外部处理 | API/GraphQL 编辑器可配置 Digest 与 OAuth2 Client Credentials；支持 token endpoint 两种认证方式、scope/audience、变量渲染、单场景缓存和安全错误摘要 | 本地已实现并有回归；`backend/app/services/api_auth.py`、`CaseFormDrawer.vue`；真实 Token Endpoint/Digest challenge 待验收 |
| API 场景编排 | 多步骤 API 缺少可视化依赖、失败策略和上下文边界 | 编辑器展示步骤关系并可追加步骤；Worker 支持 `depends_on`、失败停止/依赖跳过、步骤/场景上下文和登录态生命周期 | 已实现；`backend/app/services/api_scenario.py`、`CaseFormDrawer.vue` |
| 数据集参数组合 | 仅支持顺序、随机、固定次数 | 支持笛卡尔积、Pairwise、组合字段、最大迭代次数和嵌套脱敏；组合生成在物化前限流 | 已实现；`backend/app/services/dataset_execution.py` |
| OpenAPI/Postman 导入 | 解析后逐条创建，冲突和半成品风险较高 | 支持预览、同名/重复检测、跳过冲突和一次事务提交；异常自动回滚；AI 导入复用同一流程；项目级 Schema、Provider/Consumer 契约资产可保存、版本化、复用和比较 | 已实现；`/cases/import-preview`、`/cases/import`、`/system/api-contract-assets` |
| Web 浏览器与分辨率 | 浏览器和 viewport 可单独配置 | Chromium/Firefox/WebKit 与 viewport/device 参数可组合，矩阵子运行使用独立会话并发执行并汇总 | 已实现；`backend/app/services/web_matrix.py`、Web Worker |
| Web 浏览器网络隔离 | 仅校验初始 URL，重定向和页面子资源可能绕过校验 | BrowserContext 逐请求校验 HTTP/HTTPS/WS/WSS，阻止私网/本机/保留地址，记录脱敏阻断证据；浏览器内部协议不发起网络连接 | 本地已实现并有回归；`backend/app/services/web_network_guard.py`、Web Worker、录制 API；专用 Worker/部署网络策略仍待验收 |
| Web 页面资产/POM | 低代码步骤重复录入定位器，POM 不能直接执行 | 元素资产、备用定位器、页面对象 CRUD，低代码 `page_object` 展开执行并校验项目边界 | 已实现；`/system/web-assets`、Web Worker |
| Web 文件操作 | 文件步骤无统一上传/下载资产入口 | 项目级文件上传、MinIO 对象引用、上传到 `<input>`、下载等待和运行附件归档 | 已实现；`/projects/{id}/web-files` |
| Web 视觉回归 | 只有截图，没有基线差异 | PNG 基线、像素阈值、忽略区域、差异图和 `visual_assert` 步骤 | 已实现；`WebVisualBaseline`、`web_visuals.py` |
| Web 定位器失效修复 | 失败后只有诊断/备用定位器回退 | 失败资产可生成候选定位器、置信度和来源；用户确认后才写回、递增版本并可回归验证 | 已实现；`repair-preview`，默认不自动改写 |
| Android 设备工程化 | 有租约和标准安装/启动，但缺少矩阵并行与统一产物 | 设备信息、logcat、可选 MP4 录屏归档；系统动作、网络/权限/旋转/前后台；设备兼容矩阵通过独立数据库会话和独立租约并行执行并汇总，运行详情展示设备级结果并可跳转子运行 | 本地代码已实现；真实 ADB 设备池并发、抢占和故障恢复验收仍待完成 |
| iOS/Appium | 无 iOS 执行链 | 增加 `IosDevice`/`IosApp` 资产、IPA 项目隔离 API、iOS 设备租约、专用队列和 W3C Appium/XCUITest Worker；支持脚本/低代码步骤、截图、录屏和 syslog 产物 | 部分实现；需要 macOS、Xcode、Appium/XCUITest、签名应用和真实设备联调 |
| 性能自动阶梯 | 只能手工配置 stages | `auto_ramp` 根据起始并发、步长、最大并发自动生成有界 stages，并写入选项快照 | 已实现；`performance_ramp.py` |
| 性能目标服务指标 | 只有 Worker/平台自身采样边界 | 性能中心支持 Prometheus URL/环境变量、查询超时和多条 PromQL；后端最多 8 条查询并限制响应大小，目标指标作为独立样本归档；Windows 本地 Prometheus 与 k6 run 已完成关联验收 | 部分实现；生产 Prometheus、真实外部目标和长期历史仍待验收，证据见 `docs/evidence/performance-windows-local-prometheus-target-metrics-2026-08-12.json` |
| JMeter | 可执行 JMX 并解析 JTL，缺少报告附件 | 可选生成 JMeter HTML 报告并压缩上传到 MinIO，同时保留统一 JTL 摘要 | 已实现；`performance_jmeter.py` |
| 性能分布式/容量/通知 | 多节点和容量分析链路不完整 | 节点分片、父子运行聚合、容量分析、阈值/基线/节点异常通知摘要已接入 | 部分实现；需要真实节点和外部通知渠道验收 |

## 当前仍需完成的任务

1. 在真实 Android 设备或模拟器上验收矩阵、租约并发、录屏、权限、网络、旋转和 logcat 产物。
2. 在 macOS Worker 上部署 Xcode、Appium 2/XCUITest、签名 IPA 和 iPhone/Simulator，完成已实现 iOS HTTP 协议执行链的真实最小闭环。
3. 在真实外部目标和生产 Prometheus 上确认目标查询、时间线、权限、超时、告警和长期 SLO 历史；Windows 本地回环闭环已完成，不替代该验收。
4. 在 Docker Worker 中安装并验收 Firefox/WebKit/JMeter，完成三浏览器和 JMeter HTML 外部回归。
5. 外部/远程 OpenAPI `$ref` 已补齐发布策略：解析接口和 UI 支持 `warn`（默认，仅提示不联网）与 `reject`（发布安全模式，发现外部引用即拒绝）；真实 Provider/Consumer 规格联调，以及 OAuth2 Token Endpoint、Digest challenge、超时和凭据轮换仍待外部环境提供真实服务。其余本地 `$ref` 解析、契约资产 CRUD/版本化、Schema 资产复用、资产管理 UI、API 场景编排和现有关键页面 E2E 已实现/验收。
6. 本地全量后端、前端单元测试、Playwright E2E、类型检查、构建、迁移链、Bandit、pip-audit 和 npm audit 已完成；真实环境验收仍需按发布环境执行。

## 当前开发机环境探测

- Windows 上已检测到 ADB 37.0.0，但 `adb devices` 当前没有在线设备；Android 真实设备矩阵因此不能在本机宣称已验收。
- 已检测到 JMeter 5.6.3；Docker 命令不可用，因此 Docker Worker、分布式节点和容器内浏览器/JMeter 仍需部署环境。
- JMeter 5.6.3 最近一次实际执行 `deploy/performance-acceptance/jmeter_smoke.jmx`：请求本地 `/login` 1 次、错误数 0，并生成 JTL 与 HTML 报告，证据目录为 `.local-run/jmeter-smoke-20260811-233647/`；该结果不替代 Docker Worker 外部验收。
- Playwright 1.61.1 及 Chromium、Firefox、WebKit 浏览器缓存可用，本轮通过 `frontend/tools/browser-matrix-smoke.mjs` 等待交互元素后，三者均访问本地 `/login` 返回 HTTP 200 且检测到 4 个输入框；这不等同于目标 Docker Worker 验收。
- 本机 Prometheus 已安装为用户级 Windows 工具并在 `127.0.0.1:9090` ready，已抓取 ATP Backend `/metrics` 并完成目标指标 run 关联证据；这不等同于生产 Prometheus 连续历史。iOS/Appium 仍必须转移到 macOS + Xcode + WDA + 签名 IPA + iPhone/Simulator。
- 已对已授权 Linux 主机做只读探测：ARM64、Docker 29.3.0 可用，主机已有健康的 PostgreSQL/Redis/MinIO 容器，但未发现 ATP 验收栈或 Prometheus 9090；为避免覆盖现有业务，未在该主机部署或重启任何服务。

## 2026-08-13 审计日志与本地质量核验

- 管理员审计日志已支持项目、用户、动作和 ISO-8601 时间范围筛选；新增受限 CSV 导出，页面最多 5000 条、服务端最多 10000 条，使用 UTF-8 BOM 并防护表格公式注入。
- 成功导出写入 JSON 编码的 `audit_log_export` 审计事件，页面动作筛选包含 `audit_log_cleanup` / `audit_log_export`；导出审批、归档和进一步脱敏仍需生产策略确认。
- 后端完整非集成回归的最新记录为 `2018 passed`，覆盖率 `82.03%`（门禁 82%），`269` 个测试文件逐文件独立通过；前端 Vitest `47 files / 199 tests passed`，type-check 和生产构建通过。
- 本轮审计 API 定向回归 `4 passed`，Ruff 和 `git diff --check` 通过；Linux/Kubernetes、真实通知渠道、Android/iOS 和外部 API 仍需目标环境证据。

## 2026-08-13 发布前质量门禁复核

- Python 3.12.11 后端完整回归 `2018 passed`，覆盖率 `82.03%`（门禁 82%），`269` 个测试文件逐文件独立通过；前端 `47 files / 199 tests passed`。
- Python 3.14.3 条件依赖环境下完整非集成后端回归同样为 `2018 passed`；覆盖率门禁以 Python 3.12.11 为准。
- Bandit、npm audit、pip-audit（锁定 requirements、`--disable-pip --no-deps`）和仓库 pre-commit 全量通过；部署配置校验通过。
- Docker Compose/Helm lint 因当前 Windows 未安装命令而跳过，不作为真实集群部署证据；Linux/Kubernetes、真实通知渠道、Android/iOS 和外部 API 仍待目标环境。

## 2026-08-12 最新本地质量核验

- 后端非集成测试：`1886 passed`；Python 3.12 `--cov-fail-under=82` 基线 `82.13%` 通过（使用 `--ignore=backend/tests/integration`，符合仓库对集成环境变量的保护约定）。
- 前端 Vitest：`44 files / 177 tests passed`；覆盖率 statements/branches/functions/lines 为 `36.25% / 31.37% / 28.58% / 37.83%`，`vue-tsc --noEmit` 和生产构建通过。
- Python 质量门禁：mypy `132 source files` 无错误；Ruff lint、格式检查、Bandit（无高/中风险）、pip-audit 和 `git diff --check` 通过；npm audit 报告 `0 vulnerabilities`。
- Windows 启动档案/Android Worker 定向回归：`10 passed`；逐文件后端门禁 `256 passed, 0 failed`。
- 前端 E2E：`10 passed`（登录、Dashboard、用例、执行、Run 详情、套件、计划和 Windows 下载夹具）；契约资产页面组件回归 `3 passed`，并完成真实浏览器抽查。
- 当前结论：本地代码实现和自动化验证已完成；Android/iOS、生产 Prometheus/SLO 历史、Firefox/WebKit/JMeter Worker、真实通知渠道、真实 API 联调和外部 Provider/Consumer 规格仍属于发布前验收，不将 mock E2E 或本地回环结果冒充真实环境结论。

## 代码入口速查

- API：`backend/app/worker/executors/api_executor.py`、`backend/app/services/execution_contract.py`、`backend/app/services/safe_expressions.py`、`backend/app/services/api_contracts.py`、`backend/app/api/v1/api_contract_assets.py`
- Web：`backend/app/worker/executors/web_lowcode_executor.py`、`backend/app/services/web_matrix.py`、`backend/app/services/web_visuals.py`、`backend/app/services/web_locator_repair.py`
- Android：`backend/app/worker/executors/android_lowcode_executor.py`、`backend/app/services/device_compatibility.py`
- 性能：`backend/app/services/performance_ramp.py`、`backend/app/services/performance_target_metrics.py`、`backend/app/services/performance_jmeter.py`
- 契约资产 UI：`frontend/src/views/system/ApiContractAssetsView.vue`、`frontend/src/views/system/ApiContractAssetsView.spec.ts`
- 计划与基线：`docs/implementation-plan-2026-Q18-capability-expansion.md`、`docs/capability-baseline-2026-08-07.md`、`docs/q18-implementation-log-2026-08-07.md`
## 2026-08-11 覆盖率收口补充

- 后端非集成测试更新为 `1827 passed`，Python 3.12 覆盖率 `82.50%`，Python 3.14 覆盖率 `82.05%`，两套解释器均通过覆盖率门禁；252 个测试文件逐文件独立运行全部通过。
- 前端新增项目列表、用户管理和个人资料页面的组件级行为回归，修复项目导入成功后的状态清理缺陷；全量 `40 files / 157 tests passed`。
- 前端覆盖率达到 statements/branches/functions/lines `31.54% / 26.53% / 24.73% / 32.76%`，超过 Vitest 现有门禁 `31.5 / 26.5 / 24.5 / 32.5`；type-check 和生产构建通过。

## 2026-08-11 Python 3.14 兼容性与覆盖率复验

- 为 Python 3.14 准备独立虚拟环境并验证运行时依赖；`asyncpg 0.31.0`、`psycopg2-binary 2.9.12` 和 `PyYAML 6.0.3` 均使用可用二进制包，`pip check` 通过。
- 后端 Python 3.14.3 非集成回归 `1827 passed`，覆盖率 `82.05%`，`--cov-fail-under=82` 通过。
- 后端 Python 3.12.11 对照回归 `1827 passed`，覆盖率 `82.50%`，`--cov-fail-under=82` 通过；252 个测试文件在 Python 3.14 下逐文件独立运行 `252 passed, 0 failed`。
- 新增覆盖录制会话生命周期、路由异常、资产持久化冲突、用户查询/角色/重复数据/管理员保护等边界回归；Ruff、format-check、mypy 和 `git diff --check` 通过。

## 2026-08-11 低代码 Python 脚本生成补齐

- WebCaseDrawer 打开时加载当前项目的元素资产和页面对象，生成 Python 时将 `element_asset_id` 和 `page_object_id` 展开为独立 Playwright 定位器与动作。
- Web 生成器新增文件上传、下载等待/保存、视觉基线像素差异断言；上传文件、下载目标和视觉基线通过 `ATP_WEB_UPLOAD_N`、`ATP_WEB_DOWNLOAD_N`、`ATP_VISUAL_BASELINE_N` 环境变量传入，保持脚本脱离平台后仍可执行。
- 缺少定位器、未加载的页面对象、空公共动作或未知动作不再生成注释后继续执行，而是生成明确的 `pytest.fail`；Android 生成器同时覆盖旋转、权限、网络配置和前后台切换。前端定向生成器测试 6 项，全量 `40 files / 161 tests passed`，coverage `31.94% / 27.09% / 24.94% / 33.21%`，type-check/build 通过。
