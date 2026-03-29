# ATP - 自动化测试平台 产品需求文档

**版本**: v1.0
**日期**: 2026-03-03
**项目代号**: ATP (Automated Testing Platform)

---

## 1. 项目背景与目标

### 1.1 背景

当前测试工作面临以下痛点：
- Web 自动化、接口测试、移动端 UI 测试分散在不同工具中，缺乏统一管理
- 测试用例分散在脚本文件中，难以团队共享和复用
- 测试执行结果缺乏统一的可视化报告
- 有编程能力的测试工程师和低代码业务测试人员无法在同一平台协作

### 1.2 目标

构建一个统一的自动化测试平台，支持：
- **Web UI 测试**（Selenium/Playwright）
- **接口测试**（REST / WebSocket / GraphQL / gRPC）
- **Android 移动端 UI 测试**（uiautomator2）
- **用例统一管理**、调度执行、报告展示

> 说明：当前仓库中的核心主线能力已基本落地；本文档更偏向产品目标与范围定义，实际实现状态请以 `README.md`、`Task.md` 与 `docs/` 中运行说明为准。

### 1.3 核心价值

| 用户角色 | 价值 |
|---------|------|
| 测试工程师（有编程能力） | 脚本统一管理、快速调试、CI/CD 接入 |
| 业务测试人员（低代码） | 可视化配置用例、无需写代码即可执行测试 |

---

## 2. 用户角色

| 角色 | 描述 | 权限范围 |
|------|------|---------|
| **超级管理员** | 平台所有者 | 全部权限 |
| **测试工程师** | 负责脚本编写和框架维护 | 创建/编辑/执行所有用例 |
| **业务测试人员** | 负责业务场景验证 | 配置用例、查看报告 |
| **只读成员** | 观察者 | 仅查看报告 |

---

## 3. 功能模块

### 3.1 用例管理

#### 3.1.1 用例目录与分组
- 支持树形目录结构（项目 → 模块 → 用例）
- 支持跨模块引用用例
- 支持批量操作（移动、复制、删除）

#### 3.1.2 用例标签系统
- 自定义标签（如：`smoke`、`regression`、`p0`、`p1`）
- 标签维度：优先级 / 环境 / 业务域 / 自定义
- 支持多标签过滤与搜索

#### 3.1.3 用例类型

| 类型 | 创建方式 | 说明 |
|------|---------|------|
| Web UI 测试 | 脚本上传 / 可视化录制 | 基于 Playwright/Selenium |
| 接口测试 | 表单配置 | 支持 REST / WebSocket / GraphQL / gRPC |
| Android UI 测试 | 脚本上传 / 可视化配置 | 基于 uiautomator2 |

#### 3.1.4 用例版本管理
- 用例支持版本历史，可回滚到历史版本
- 记录每次修改人和修改时间

---

### 3.2 Web UI 测试

#### 3.2.1 测试脚本管理
- 支持上传 Python 脚本（Playwright + pytest）
- 脚本通过 `pytest` 命令执行，结果通过 `pytest-json-report` 解析回平台
- 在线代码编辑器（Monaco Editor）
- 脚本依赖配置（requirements.txt）

#### 3.2.2 可视化低代码模式
- 步骤式录制（操作：点击、输入、断言、等待等）
- 支持选择器配置（CSS / XPath / 文本）
- 步骤可拖拽排序

#### 3.2.3 执行配置
- 浏览器类型：Chromium / Firefox / WebKit（Playwright）
- 分辨率配置
- 无头/有头模式
- 超时配置

---

### 3.3 接口测试

#### 3.3.1 HTTP/REST 测试
- 请求配置：URL、Method、Headers、Query Params、Body（JSON / Form / Raw）
- 认证：Basic Auth / Bearer Token / API Key / OAuth2
- 断言：状态码 / 响应体 JSONPath / 响应头 / 响应时间
- 变量提取：从响应中提取值供后续用例使用

#### 3.3.2 GraphQL 测试
- Query / Mutation / Subscription 支持
- Schema introspection 自动补全
- 变量配置

#### 3.3.3 WebSocket 测试
- 建立连接配置
- 发送消息序列
- 接收消息断言
- 超时 / 重连配置

#### 3.3.4 gRPC 测试
- 上传 `.proto` 文件
- 方法选择与参数配置（Unary / Server Streaming / Client Streaming / Bidirectional）
- 响应断言

#### 3.3.5 接口测试公共能力
- **环境管理**：开发 / 测试 / 预发 / 生产环境变量
- **前置/后置脚本**：Python 脚本执行
- **用例链**：前一个接口的响应可作为后一个接口的入参
- **Mock 支持**：内置 Mock Server、规则管理页面与基础请求日志能力已落地，后续可继续增强条件响应与批量导入导出

---

### 3.4 Android UI 测试

#### 3.4.1 设备管理
- 接入真机列表（通过 ADB 连接）
- 设备状态监控（在线/离线）
- 设备分组（用于并行执行）

#### 3.4.2 测试脚本管理
- 支持上传 Python 脚本（uiautomator2 + pytest）
- 脚本通过 `pytest` 命令执行，结果通过 `pytest-json-report` 解析回平台
- 在线代码编辑器
- APK 包管理（上传、版本管理）

#### 3.4.3 可视化低代码模式
- 设备实时屏幕镜像（WebRTC/MJPEG）
- 点击元素自动生成操作步骤
- 常用操作：点击、长按、滑动、输入、截图断言

#### 3.4.4 执行配置
- 选择目标设备或设备组
- APK 版本选择
- 自动安装 APK
- 截图失败截图保留

---

### 3.5 测试套件管理

- 将多个用例（可跨类型）组合为一个测试套件
- 套件内用例可配置执行顺序或并行执行
- 支持数据驱动：CSV / JSON 参数化
- 套件共享数据：全局变量、Fixtures

---

### 3.6 测试计划与调度

#### 3.6.1 手动执行
- 选择用例/套件 → 选择环境 → 立即执行

#### 3.6.2 定时调度
- Cron 表达式配置
- 定时执行指定测试套件
- 执行完成后通知（邮件 / 企业微信 / 钉钉）

#### 3.6.3 触发执行
- Webhook 触发（供 CI/CD 系统调用）
- 支持传入动态参数（如：版本号、环境）

---

### 3.7 CI/CD 集成

#### 3.7.1 Jenkins 集成
- 提供 Jenkins Plugin 或调用 REST API 触发测试
- 测试结果 JUnit XML 格式输出（供 Jenkins 解析）

#### 3.7.2 GitLab CI 集成
- 提供 `.gitlab-ci.yml` 模板
- 支持 Merge Request 触发特定套件执行

#### 3.7.3 通用 REST API
- 所有功能提供 REST API，供任意 CI/CD 系统集成
- API Key 认证

---

### 3.8 执行引擎与任务队列

- 基于 Celery + Redis 的异步任务队列
- 支持并行执行多个测试任务
- 执行节点（Worker）可横向扩展
- 任务状态实时推送（WebSocket）

#### 脚本类用例执行流程（Web UI / Android）

工程师上传的 pytest 脚本通过以下流程执行：

```
Worker 收到任务
  → 从 MinIO 下载脚本文件到临时目录
  → 调用 pytest 命令执行
      pytest test_case.py --json-report --json-report-file=result.json
  → 解析 result.json（pytest-json-report 格式）
  → 将步骤结果、截图路径写入数据库
  → 上传截图到 MinIO
  → 推送执行结果到前端（WebSocket）
  → 清理临时目录
```

#### 低代码用例执行流程（接口测试 / 可视化配置用例）

```
Worker 收到任务
  → 从数据库读取步骤配置
  → 直接调用对应执行器（httpx / Playwright API / uiautomator2 API）
  → 逐步记录结果和截图
  → 写入数据库 + 推送 WebSocket
```

---

### 3.9 报告与统计

#### 3.9.1 执行报告
- 执行总览：通过/失败/跳过/错误 统计
- 用例级详情：请求/响应、步骤截图、错误信息、执行耗时
- 失败截图/录像（Web UI / Android）
- 报告导出：HTML / PDF（当前单用例已实现，套件 / 计划级 HTML / PDF 仍可继续补强）

#### 3.9.2 统计看板
- 用例通过率趋势图（按天/周/月）
- 各模块缺陷分布
- 执行时长趋势
- 最近失败用例 Top 10
- 当前已具备聚合接口与前端看板页面，后续可继续扩展更多统计维度与缓存优化

#### 3.9.3 缺陷追踪（可选集成）
- 失败用例一键创建 Jira / 禅道 Issue
- 当前已具备基础缺陷跟踪配置与一键创建能力，后续可继续补充截图附件、重复缺陷检测与状态同步

---

### 3.10 系统管理

- 用户管理：创建/禁用用户、角色分配
- 环境配置：全局环境变量管理
- 通知配置：邮件 SMTP / 企业微信机器人 / 钉钉机器人
- 操作日志：记录关键操作（谁在什么时间做了什么）
- 系统设置：超时默认值、并发数限制等

---

## 4. 技术架构

### 4.1 整体架构

```
┌─────────────────────────────────────────┐
│              前端 (Vue 3)               │
│  用例管理 | 执行报告 | 设备管理 | 系统管理  │
└──────────────────┬──────────────────────┘
                   │ HTTP / WebSocket
┌──────────────────▼──────────────────────┐
│           后端 API (FastAPI)            │
│  用例 CRUD | 执行调度 | 报告查询 | 认证   │
└──────┬──────────────────────────────────┘
       │ Celery Task
┌──────▼──────────────────────────────────┐
│           执行引擎 (Worker)              │
│  Playwright | uiautomator2 | httpx | gRPC     │
└──────────────────┬──────────────────────┘
                   │
       ┌───────────┼───────────────┐
  PostgreSQL     Redis         MinIO
  (业务数据)    (任务队列/缓存)  (报告/截图/文件)
```

### 4.2 技术选型

| 层级 | 技术 | 版本要求 |
|------|------|---------|
| **前端框架** | Vue 3 + TypeScript | Vue 3.4+ |
| **前端组件库** | Ant Design Vue 或 Element Plus | - |
| **前端构建** | Vite | 5.x |
| **后端框架** | FastAPI | 0.110+ |
| **任务队列** | Celery + Redis | Celery 5.x |
| **ORM** | SQLAlchemy 2.x (async) | 2.0+ |
| **数据库** | PostgreSQL | 15+ |
| **缓存/队列** | Redis | 7.x |
| **文件存储** | MinIO（本地对象存储） | - |
| **Web 测试** | Playwright (Python) + pytest | 1.40+ |
| **移动测试** | uiautomator2 | 3.x |
| **接口测试** | httpx / websockets / grpcio | - |
| **脚本执行器** | pytest + pytest-json-report | pytest 8.x |
| **认证** | JWT (python-jose) | - |
| **部署** | Docker Compose | - |

### 4.3 部署架构（本地私有化）

```yaml
# docker-compose 服务清单
services:
  frontend:     # Nginx 托管 Vue 构建产物
  backend:      # FastAPI 应用
  worker:       # Celery Worker（可多实例）
  beat:         # Celery Beat（定时任务调度器）
  postgres:     # PostgreSQL 数据库
  redis:        # Redis
  minio:        # 对象存储（报告/截图）
  flower:       # Celery 任务监控（可选）
```

---

## 5. 数据模型（核心实体）

```
Project（项目）
  └── Module（模块/目录）
        └── TestCase（测试用例）
              ├── WebTestCase（Web UI 用例详情）
              ├── ApiTestCase（接口用例详情）
              └── AndroidTestCase（Android 用例详情）

TestSuite（测试套件）
  └── SuiteCase（套件-用例关联，含顺序）

TestPlan（测试计划）
  └── PlanSuite（计划-套件关联）

TestRun（执行记录）
  └── CaseResult（单用例结果）
        └── StepResult（单步骤结果，含截图）

Device（设备）
Environment（环境）
  └── EnvVariable（环境变量）
User（用户）
  └── Role（角色）
```

---

## 6. 分阶段开发计划

### Phase 1 - 基础框架（MVP）

**目标**: 跑通主流程，可实际使用

- [ ] 项目初始化（前后端脚手架、Docker Compose 配置）
- [ ] 用户认证（登录 / JWT / 角色权限）
- [ ] 项目/模块/用例 CRUD 基础管理
- [ ] **接口测试（HTTP REST）**：配置 → 执行 → 报告
- [ ] 执行引擎（Celery）基础框架
- [ ] 简单执行报告页面

### Phase 2 - Web UI 测试

- [ ] Playwright 执行器集成
- [ ] 脚本上传与在线编辑
- [ ] Web 用例低代码配置
- [ ] 执行报告：步骤截图/录像

### Phase 3 - Android 测试

- [ ] uiautomator2 执行器集成
- [ ] ADB 设备发现与管理
- [ ] APK 上传与管理
- [ ] 设备屏幕镜像（MJPEG Stream）
- [ ] Android 用例低代码配置

### Phase 4 - 高级功能

- [ ] 接口测试：GraphQL / WebSocket / gRPC 支持
- [ ] 测试套件与测试计划
- [ ] 定时调度（Celery Beat）
- [ ] CI/CD Webhook 集成
- [ ] 统计看板
- [ ] 通知集成（邮件/企业微信）

### Phase 5 - 完善与优化

- [ ] 接口测试 Mock Server
- [ ] 缺陷跟踪集成（Jira/禅道）
- [ ] 报告导出（HTML/PDF）
- [ ] 用例版本历史
- [ ] 性能优化与安全加固

---

## 7. API 设计规范

### 7.1 基础约定
- 基础路径：`/api/v1/`
- 认证：`Authorization: Bearer <JWT Token>`
- 响应格式：
  ```json
  {
    "code": 0,
    "message": "success",
    "data": { ... }
  }
  ```

### 7.2 核心 API 端点（部分）

| Method | Path | 说明 |
|--------|------|------|
| POST | `/auth/login` | 登录获取 Token |
| GET | `/projects` | 获取项目列表 |
| GET | `/cases?module_id=&type=&tag=` | 用例列表（带过滤） |
| POST | `/cases` | 创建用例 |
| POST | `/cases/{id}/run` | 执行单个用例 |
| POST | `/suites/{id}/run` | 执行套件 |
| GET | `/runs/{id}` | 获取执行结果 |
| GET | `/runs/{id}/report` | 获取 HTML 报告 |
| POST | `/webhook/trigger` | CI/CD 触发接口 |
| GET | `/devices` | Android 设备列表 |

---

## 8. 非功能性需求

| 指标 | 要求 |
|------|------|
| **可用性** | 私有化部署，服务异常可快速重启 |
| **并发执行** | 默认支持 5 个测试任务并行，可通过增加 Worker 实例扩展 |
| **接口响应** | 普通查询 API < 200ms |
| **文件存储** | 截图/报告保留 90 天（可配置） |
| **安全性** | JWT 过期机制、API Key 管理、敏感配置加密存储 |
| **可观测** | Worker 任务监控（Flower）、日志统一收集 |
| **可维护** | Docker Compose 一键部署，.env 文件统一配置 |

---

## 9. 目录结构规划

```
ATP/
├── frontend/               # Vue 3 前端
│   ├── src/
│   │   ├── views/          # 页面
│   │   ├── components/     # 通用组件
│   │   ├── stores/         # Pinia 状态管理
│   │   ├── api/            # API 调用封装
│   │   └── router/         # 路由
│   └── vite.config.ts
│
├── backend/                # FastAPI 后端
│   ├── app/
│   │   ├── api/            # 路由层
│   │   ├── services/       # 业务逻辑层
│   │   ├── models/         # 数据库模型（SQLAlchemy）
│   │   ├── schemas/        # 请求/响应 Schema（Pydantic）
│   │   ├── core/           # 配置、认证、安全
│   │   └── worker/         # Celery 任务定义
│   │       ├── executors/  # 执行器：web/api/android
│   │       └── tasks.py
│   ├── alembic/            # 数据库迁移
│   └── requirements.txt
│
├── docker/                 # Docker 配置
│   ├── nginx.conf
│   └── ...
├── docker-compose.yml
├── docker-compose.dev.yml  # 开发环境
└── .env.example
```

---

## 10. 开发启动建议

### 建议开发顺序
1. 搭建 `docker-compose` 基础环境（PostgreSQL / Redis / MinIO）
2. FastAPI 项目初始化：用户认证 + 项目/模块/用例 CRUD
3. Vue 3 前端初始化：登录页 + 用例管理页面
4. 接入 Celery 执行引擎，实现第一个 HTTP 接口测试用例的完整执行链路
5. 逐步扩展其他测试类型和功能模块

### 关键技术验证点（建议优先 PoC）
- Playwright Python 在 Docker 容器中的无头运行（配合 pytest-playwright）
- uiautomator2 通过 ADB over TCP 连接宿主机真机（Worker 容器内调用宿主机设备）
- pytest-json-report 结果解析与平台报告的字段映射
- MinIO 文件上传与预签名 URL 访问
- WebSocket 实时推送任务状态到前端
