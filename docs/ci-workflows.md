# GitHub Actions 工作流说明

本文记录仓库当前 CI / E2E / integration / release readiness 工作流的触发条件、依赖服务和常见失败排查方式。

## `ci.yml` — 主 CI

- **触发**：push 到 `main`；针对 `main` 的 pull request。
- **Jobs**：
  - `Backend lint`：安装 `backend/requirements.txt` + `backend/requirements-dev.txt`，运行 `python -m ruff check` 与 `python -m ruff format --check`（覆盖 `backend/app`、`backend/tests` 与 `scripts/` 下受检脚本，清单以 Makefile 的 `LINT_SCRIPTS` 为准）。同一 job 也运行 `python -m mypy` 与 `python -m bandit -c pyproject.toml -r backend/app -ll`。**运行时依赖必须装**：只装 `requirements-dev.txt` 时 mypy 看不到 SQLAlchemy 的真实签名，`d116359^` 的 `run_retention.py` 只报 8 个错而完整环境报 12 个。
  - `Empty database migration`：启动干净 PostgreSQL 16，执行 `cd backend && alembic upgrade head`。
  - `Backend pytest`：启动 PostgreSQL 16 + Redis 7，运行后端主回归并产出覆盖率 XML：`python -m pytest backend/tests -q --ignore=backend/tests/integration --cov=backend/app --cov-report=xml --cov-report=term-missing:skip-covered --cov-fail-under=70`。同一 job 随后运行 `python scripts/pytest-standalone-sweep.py --jobs 4`，逐文件单独跑一遍全部非 integration 测试。
  - `Backend pytest (Windows)`：`windows-latest` + Python 3.12，只跑后端单元回归 `python -m pytest backend/tests -q --ignore=backend/tests/integration`。**不起 service container**（单元套件已 stub 掉 postgres/redis/minio），**不跑覆盖率门禁**（覆盖率在 Linux job 测一遍即可），**不跑单文件扫描**（184 次进程启动在 Windows 上过慢，且它查的是测试间耦合，与平台无关）。存在理由见下方「Windows job 的范围」。
  - `Frontend type-check + build`：运行 `npm ci`、`npm run test:coverage`、`npm run type-check`、`npm run build`；前端门禁为 statements `20.5%`、branches `17.5%`、functions `16.5%`、lines `21.0%`（定义在 `frontend/vitest.config.ts`，调整规则见 `docs/coverage-baseline-2026-q13.md`）。
- **Artifacts**：`Backend pytest` 上传 `coverage.xml` 为 `backend-coverage-xml`；前端 job 上传 `frontend/coverage` 为 `frontend-coverage-report`。
- **依赖服务**：PostgreSQL、Redis；MinIO 相关能力在主 CI 里通过测试 stub 覆盖，真实 MinIO 放在 integration workflow。
- **常见排查**：
  - 迁移失败：先本地执行 `make infra-up && make migrate`，检查新增迁移的 `down_revision`、枚举、索引和约束是否能从空库创建。
  - lint 失败：先运行 `make lint PYTHON=backend/.venv/bin/python`，当前门禁聚焦未定义名称相关规则。
  - format 失败：先运行 `make format PYTHON=backend/.venv/bin/python`，再用 `make format-check PYTHON=backend/.venv/bin/python` 复验。
  - mypy 失败：先运行 `make mypy PYTHON=backend/.venv/bin/python`，当前覆盖 `core` / `schemas` / `services`。
  - Bandit 失败：先运行 `make security-bandit PYTHON=backend/.venv/bin/python`，当前 medium/high 阻断，low 仅记录。
  - 依赖漏洞扫描：先运行 `make security-pip-audit PYTHON=backend/.venv/bin/python` 与 `make security-npm-audit`。当前 pip/npm 依赖扫描已清零，后续可接入 high/critical 阻断型 CI。
  - 后端测试失败：确认失败用例是否属于真实基础设施测试；integration 用例应放在 `backend/tests/integration` 并带 `integration` marker。
  - 覆盖率失败：先运行 `make test-backend-coverage PYTHON=backend/.venv/bin/python`，确认总覆盖率不低于当前 `--cov-fail-under=70` 门槛。
  - 单文件扫描失败：某个测试文件只有在整套按序运行时才通过（典型原因是依赖别的文件先把 `backend/` 插进 `sys.path`，或先 hard-set 了更全的 stub）。本地复现：`make test-backend-standalone PYTHON=backend/.venv/bin/python`，或直接 `python -m pytest <该文件> -q`。修法是把缺失的引导补进 `backend/tests/conftest.py`，而不是在该文件里再抄一遍。
  - Windows job 失败而 Linux 绿：这是该 job 存在的意义，按平台假设排查而不是加 skip。常见来源是路径分隔符（断言里写死 `/`，生产代码用 `pathlib` 拼出的是 `\`）、文本读写未显式 `encoding="utf-8"`（Windows 默认走 locale 编码，本仓库大量中文内容会直接炸）、以及 `NamedTemporaryFile` 在未关闭时无法二次打开。
  - 前端单测或覆盖率失败：先运行 `cd frontend && npm run test:coverage`，当前门禁用于防止已覆盖切片回退，后续随 Q12 测试增长逐步提高。
  - 前端构建失败：先运行 `cd frontend && npm run type-check` 定位 TypeScript 错误，再运行 `npm run build` 验证产物。

## Windows job 的范围（Q15-03）

`docs/windows-local-run.md` 与 `scripts/windows-local.ps1` 把 Windows 列为受支持的
开发平台，但在 Q15-03 之前 `.github/workflows/` 下每个 workflow 都只跑 Linux。

2026-07-31 第一次在 Windows 上跑全套后端测试，当场撞出一个只在该平台失败的用例：
`worker/test_q12_evidence_collector.py` 的 fake 用
`endswith("scripts/android-network-doctor.sh")` 匹配参数，而
`collect-q12-evidence.py:817` 用 `pathlib` 拼这个参数，Windows 下是反斜杠。该问题
修于 `d116359`。随后扫描确认套件里其余四处 `endswith("<path>/…")` 断言都是 URL 路径
而非文件系统路径，所以*已知*影响面就这一个 —— 但没有任何机制拦住下一个，而且没有
这个 job 谁也不会从 CI 得知。

**刻意排除项：**

| 不在 Windows 跑 | 原因 |
| --- | --- |
| integration 测试 | 需要真实 PostgreSQL / Redis / MinIO，仍由 `test-integration.yml` 在 Linux 上跑 |
| Playwright E2E | 浏览器矩阵成本高，且 `test-e2e.yml` 已覆盖，平台差异不在被测范围内 |
| 覆盖率门禁 | 覆盖率是代码属性不是平台属性，在 Linux job 测一遍即可，避免两处门禁漂移 |
| 单文件扫描 | 184 次进程启动在 Windows 上过慢；它查的是测试间隐式耦合，与平台无关 |
| lint / mypy / bandit | 静态检查结果与平台无关，重复跑只增加 CI 时长 |

**注意**：由于 `main` 没有 required status checks（见下方「门禁强制力现状」），这个
job 和其他 job 一样只是通知性的 —— 它变红不会阻止任何一次 push。Q15-03 的验收条件
里「纳入 required 集合」这一条在当前套餐下无法满足，这里如实记录，不假称已具备。

## `test-integration.yml` — 真实基础设施集成测试

- **触发**：手动 `workflow_dispatch`；每日 UTC 03:17 定时。
- **范围**：`backend/tests/integration`，覆盖 auth、case-run、mock 等真实链路。
- **依赖服务**：PostgreSQL 16、Redis 7、MinIO 容器。
- **Flaky 治理**：仅该 workflow 启用一次有界重试（`--reruns 1 --reruns-delay 2`）。同一失败签名重复出现时，必须按 `docs/flaky-governance.md` 记录 `flaky` marker、原因与退出条件，或直接修复根因。
- **关键环境**：
  - `ATP_INTEGRATION_TESTS=1`
  - `CELERY_TASK_ALWAYS_EAGER=true`
  - `CELERY_TASK_EAGER_PROPAGATES=true`
- **常见排查**：
  - 服务未就绪：查看 `Wait for services` 步骤中 Postgres、Redis、MinIO 的健康检查输出。
  - 数据库结构异常：确认 `Run Alembic migrations` 已成功；失败时优先回到主 CI 的空库迁移 job 排查。
  - 任务未同步返回：确认测试期 Celery eager 变量没有被覆盖。

## `test-e2e.yml` — 前端 Playwright E2E

- **触发**：手动 `workflow_dispatch`；每日 UTC 03:43 定时。
- **范围**：`frontend/e2e`，使用 mock API 模式，不依赖真实后端。
- **依赖服务**：无外部服务；Playwright 会按 `frontend/playwright.config.ts` 启动前端 dev server。
- **Artifacts**：失败时上传 `frontend/playwright-report/`。
- **Flaky 治理**：Playwright 配置仅在 `CI=true` 时重试 1 次；本地 `npm run e2e` 保持零重试。重复出现的环境/时序问题按 `docs/flaky-governance.md` 记录，断言或业务回归不允许通过重试隐藏。
- **常见排查**：
  - 元素定位失败：优先下载 Playwright report，看截图、trace 和实际路由。
  - 本地复现：运行 `cd frontend && npm ci && npm run e2e`。
  - 首次环境缺浏览器：运行 `npm run e2e:install` 安装 Chromium 依赖。

## `release-readiness.yml` — 发布就绪检查

- **触发**：手动 `workflow_dispatch`；每日 UTC 19:37 定时。
- **Jobs**：
  - `Docker image build checks`：构建 backend、worker、frontend 镜像，并用 worker 镜像执行 `k6 version`。
  - `Release checklist contract`：运行 `backend/tests/worker/test_q9_release_readiness.py`（契约字符串的唯一定义处），验证 `docs/q9-release-checklist.md` 仍覆盖迁移、Helm、lint、mypy、覆盖率、安全扫描、integration、E2E 和 SLO JSON 校验项。
- **依赖服务**：无外部服务；依赖 Docker build 上下文和 Dockerfile。
- **常见排查**：
  - 镜像构建失败：先本地执行 `docker build -t atp-backend:local backend/` 或对应 frontend / worker build。
  - worker k6 检查失败：确认 `backend/Dockerfile.worker` 中仍安装并暴露 k6。
  - checklist contract 失败：运行 `python -m pytest backend/tests/worker/test_q9_release_readiness.py -q` 复现，确认发布清单没有误删迁移、Helm 或质量门禁相关步骤。

## `security.yml` — 安全扫描

- **触发**：push 到 `main`；针对 `main` 的 pull request；手动 `workflow_dispatch`；每日 UTC 20:11 定时。
- **Jobs**：
  - `Gitleaks secret scan`：使用 Gitleaks 扫描仓库历史与当前变更，发现密钥时阻断。
  - `Dependency audit`：运行 `pip-audit` 扫描后端依赖；运行 `npm audit --audit-level=high` 扫描前端依赖，high/critical 阻断。
  - `Trivy image scan`：构建 backend、worker、frontend 镜像，并用 Trivy 对 HIGH/CRITICAL 漏洞阻断。
- **常见排查**：
  - Gitleaks 失败：确认命中内容是否为真实密钥；真实密钥需轮换并移出历史，误报再加最小范围 allowlist。
  - pip-audit 失败：本地运行 `make security-pip-audit PYTHON=backend/.venv/bin/python`，优先升级有修复版本的包。
  - npm audit 失败：本地运行 `npm --prefix frontend audit --audit-level=high`，必要时补 npm `overrides` 并跑前端回归。
  - Trivy 失败：先确认漏洞是否来自基础镜像、系统包或运行时依赖；优先升级基础镜像或包版本，确认为不可修复时再评估 `ignore-unfixed` / allowlist 策略。

## `.github/dependabot.yml` — 依赖更新

- **生态**：pip (`/backend`)、npm (`/frontend`)、Docker (`/backend` + `/frontend`)、GitHub Actions (`/`)。
- **频率**：每周一 Asia/Shanghai 上午分批检查。
- **分组**：按生态聚合，降低 PR 噪音。

## 门禁强制力现状（Q15-01，实测 2026-08-01）

**结论：`main` 上不存在任何服务端强制门禁。CI 的红绿目前是通知，不是拦截。**

实测记录：

```
gh api repos/2653533859/ATP/branches/main/protection
→ 403 {"message":"Upgrade to GitHub Pro or make this repository public to enable this feature."}
gh api repos/2653533859/ATP/rulesets
→ 403（同上）
gh api repos/2653533859/ATP --jq '{visibility,private}'
→ {"visibility":"private","private":true}
```

仓库是个人账户下的 private 仓库，分支保护与 rulesets 两条路都需要 GitHub Pro
或把仓库转为 public。因此 required status checks **无法配置**，`ci.yml` 里的
`ruff format --check`、`mypy`、覆盖率门禁都不会阻止任何一次 push 或合并。

这不是理论风险，已经发生过一次：2026-07-08（`1efc10c`）起 CI 就在跑
`ruff format --check` 与 `mypy`，而 2026-07-11 的覆盖率提交引入了 16 个未格式化
文件与 `services/run_retention.py` 的 12 个 mypy 报错，在 `main` 上存活 20 天，
直到 2026-07-31 的 `e76bd24` / `d116359` 才清掉。

### 降级方案：本地钩子 + push 前自查

在服务端强制力可用之前，本仓库采用以下约定，并如实说明其边界：

1. `make setup` 会执行 `pre-commit install`，把 `.pre-commit-config.yaml` 的钩子
   装进 `.git/hooks/pre-commit`。钩子覆盖 gitleaks、ruff check、ruff format
   check、mypy 与前端 vitest。
2. mypy 钩子隔离安装自己的 mypy（不再依赖环境 `PATH` 上的 python），因此在任何
   shell 下触发 commit 都能跑出与 CI 一致的结论。
3. push 前跑 `make test-backend-coverage`、`make format-check`、`make mypy`
   （或一次 `make pre-commit` 覆盖全部文件）。
4. `backend/tests/test_quality_gate_consistency.py` 守住 Makefile、`ci.yml` 与
   `.pre-commit-config.yaml` 三处门禁数值/版本不漂移。

**这套方案能防手滑，防不了刻意绕过。** 本地钩子可以用 `--no-verify` 跳过，
CI 变红也不会阻止 push。要获得真正的强制力，只有两条路：升级 GitHub Pro，或把
仓库转为 public，然后把 `ci.yml` 的各 job 设为 required status checks。这是账户
层面的决定，不在代码范围内。

### 首次安装注意：gitleaks 钩子要下载 Go 工具链

`gitleaks` 钩子来自上游仓库且 `language: golang`，本机没有 `go` 时 pre-commit 会在
首次运行时自行下载 Go 工具链 —— 这是一次几十 MB 的网络下载，网络不稳时会失败。
2026-08-01 在本机实测连续三次失败（`IncompleteRead` /
`EOFError: Compressed file ended before the end-of-stream marker was reached`），
同日稍后重试即构建成功；环境建好后会被缓存，后续 commit 不再下载。

要留意的是 pre-commit 的行为是「任一钩子环境构建失败则整条链失败」，所以这个下载
失败期间每次 `git commit` 都会直接报错，实际效果是逼人用 `--no-verify` —— 比没装
钩子更糟。处置顺序：

- 先重试一次 `pre-commit run gitleaks --all-files`，多数情况是瞬时网络问题。
- 需要先把手上的提交做掉：`SKIP=gitleaks git commit ...`（其余钩子照常生效）。
- 网络长期不可用时的根治二选一：本机安装 Go（让上游钩子直接用本地工具链），或
  `brew install gitleaks` 后把该钩子改为 `local` + `language: system`、
  `entry: gitleaks protect --staged`（`.pre-commit-config.yaml` 的注释已写明这条
  退路）。两者都是本机环境安装，需显式决定。

CI 侧的密钥扫描走 `security.yml` 的 gitleaks-action，不受本机环境影响。

## 本地命令对照

| 目标 | 本地命令 |
| --- | --- |
| 安装依赖与本地 git 钩子 | `make setup` |
| 空库迁移 | `make infra-up && make migrate` |
| 后端 lint | `make lint` |
| 后端格式检查 | `make format-check` |
| 后端 mypy | `make mypy` |
| 后端 Bandit SAST | `make security-bandit` |
| 后端依赖漏洞扫描 | `make security-pip-audit` |
| 前端依赖漏洞扫描 | `make security-npm-audit` |
| 前端 high/critical 审计 | `cd frontend && npm audit --audit-level=high` |
| 后端主回归 | `make test-backend` |
| 后端覆盖率门禁 | `make test-backend-coverage` |
| 后端测试单文件扫描 | `make test-backend-standalone` |
| 前端单元测试 | `cd frontend && npm run test` |
| 前端类型检查 + build | `make test-frontend-build` |
| 前端 E2E | `make test-frontend-e2e` |
| 集成测试 | `make test-integration` |
| Docker 发布构建抽查 | `docker build -t atp-backend:local backend/` |

本地 `make` 默认使用 `python3`；如虚拟环境命令不同，可使用 `make PYTHON=/path/to/python test-backend`。
