# 10-29 未提交修复的回归收口（2026-10-29）

针对工作区中 10-28 审查修复与 10-29 界面/自测修复的未提交改动，补跑此前未取得结束结果的门禁。
被测对象为 `main` @ `89a38c66` 加工作区未提交改动；环境为 Windows、`backend/.venv` Python 3.12.11、Node 24.14.0。
日志与临时目录位于 `.local-run/closeout-20261029/` 与 `.pytest_tmp/`。

## 结论

后端非 API 套件、后端全部 413 个测试文件的逐文件独立运行、前端单测与类型/构建、Ruff、格式检查、mypy 全部通过。
**仍未通过的是"单个 pytest 进程跑完整个 `backend/tests`"这一形态**：它在 API 目录内存在跨文件顺序依赖并会停滞，
详见下文"未解决"。按 `CLAUDE.md` 与 `Makefile` 的定义，逐文件独立运行（`make test-backend-standalone`）是 CI 采用的隔离门禁，
该门禁本轮通过（413 个文件中 409 个一次通过，其余 4 个经换新临时目录复跑全部通过）。

## 通过项

| 范围 | 命令 | 结果 |
| --- | --- | --- |
| 已修改的后端测试文件（17 个）合并运行 | `pytest <17 files> -q` | **221 passed**，56.57s |
| 后端非 API 套件 | `pytest backend/tests --ignore=backend/tests/api --ignore=backend/tests/integration -q` | **1971 passed, 2 skipped**，399.63s |
| 后端逐文件独立扫描（全量，= `make test-backend-standalone`） | `scripts/pytest-standalone-sweep.py --jobs 4 --timeout 300` | **413 个文件：409 通过**；4 个为 Windows 临时目录锁 |
| 上述 4 个文件换新 `--basetemp` 复跑 | 逐个 `pytest <file> -q --basetemp=.pytest_tmp/rerun/<name>` | **7 / 5 / 10 / 6 passed**，合计 28 项 |
| API 逐文件独立扫描（仅该目录） | `scripts/pytest-standalone-sweep.py backend/tests/api --jobs 4 --timeout 300` | **127 个文件：126 通过**；剩余 1 个为同一 Windows 临时目录锁 |
| API 目录尾部 38 个文件 | `pytest <38 files> -v` | **355 passed**，4.63s |
| 前端单测 | `npx vitest run --pool=forks --maxWorkers=2` | **85 个文件、428 项通过**，76.90s |
| 前端类型检查与构建 | `npm run type-check` / `npm run build` | 退出码均为 0，`vite build` 4130 模块 5.86s |
| Ruff 检查 | `ruff check backend/app backend/tests <LINT_SCRIPTS>` | All checks passed |
| Ruff 格式检查 | `ruff format --check backend/app backend/tests <LINT_SCRIPTS>` | 826 files already formatted |
| mypy | `mypy backend/app/core backend/app/schemas backend/app/services` | Success，214 source files |
| 新增迁移 20261029_0083 | `pytest backend/tests/migrations/test_remote_agents_migration.py` | 升级/约束/降级回归通过（SQLite） |

对比上一轮 `self-test-2026-10-29.md` 的 1951 passed / 19 failed，非 API 套件的 19 项失败已全部消除。

## 本轮修复

### 1. 性能 API 测试的 Celery 任务绑定顺序依赖

`backend/tests/api/test_performance_api_behavior.py` 依赖模块级 `sys.modules["app.worker.tasks_performance"]` 替身，
但 `backend/app/api/v1/performance.py:90` 在**导入时**执行 `from app.worker.tasks_performance import run_performance_test`。
一旦更早的测试在运行期导入了 `app.main`（例如 `test_dual_mode_isolation.py`），
`app.api.v1.performance` 已被真实导入，模块属性绑定的是真实 Celery 任务，替身永远不生效：

```text
python -c "import app.main; from app.api.v1 import performance; print(type(performance.run_performance_test))"
-> bound_to= PromiseProxy
```

表现为 `enqueue_performance_run` 走真实 `task.delay()`，向 Redis 重连 20 次后抛
`kombu.exceptions.OperationalError: Connection closed by server.`，
`_delay_recorder.calls` 断言失败。**修复**：在 `isolate_performance_dependencies` 自动 fixture 中
额外 `monkeypatch.setattr(performance, "run_performance_test", _delay_recorder)`，与导入顺序解耦。
修复后 API 目录内该文件所在的 63% 处失败消失。

### 2. Tauri/Cargo 构建产物未纳入忽略

`frontend/src-tauri/target/`（421 个文件、约 24 MB）为未跟踪构建产物。
新增 `frontend/src-tauri/.gitignore`，忽略 `/target` 与 `/gen`；`Cargo.lock` 按 Tauri 应用惯例保留跟踪。

## Windows 临时目录锁（扫描脚本的已知噪声）

`pytest-standalone-sweep.py` 为每个文件复用固定 `--basetemp`（`.local-run/pytest-standalone/<hash>`）。
在 Windows 上，若目录仍被上一轮进程或杀毒/索引句柄占用，pytest 清理该目录时抛
`PermissionError: [WinError 5]`，表现为"文件失败"而非测试失败。
本轮 4 个失败（`test_device_agents_api.py`、`test_android_incident_archiver.py`、`test_local_schema.py`、
`test_n3_backup_restore.py`）换新 `--basetemp` 后全部通过；`Remove-Item -Recurse` 也无法删除该目录，
进一步说明是句柄占用而非断言失败。

## 未解决

单个 pytest 进程执行 `pytest backend/tests`（或 `pytest backend/tests/api`）仍不通过，且会停滞：

- 自然顺序跑到约 63% 时曾出现 5 项性能 API 失败（本轮已修复，见上）。
- 修复后在约 74% 处仍出现 5 项失败，随后进程在无 CPU 占用的情况下长时间无输出。
- 上述 5 项在"API 目录尾部 38 个文件单独运行"时 **355 项全通过**，在逐文件扫描时也全通过，
  因此属于前缀文件对后续文件的运行期污染，不是产品缺陷。
- 同一现象在 10-28/10-29 两轮自测中均已出现（`self-test-2026-10-28.md`、`self-test-repair-2026-10-29.md` 有记录）。

后续若要单进程全绿，需要把 API 目录中仍以模块级 `sys.modules["app.api.deps"]` /
`sys.modules["app.core.database"]` 覆盖建立替身的测试文件统一改为 `monkeypatch` 作用域替身
（`test_notifications.py`、`test_mock_rules.py`、`test_performance_api_behavior.py` 已是该写法）。
本轮未做这项批量重构。

## 边界

- 未运行需要 PostgreSQL、Redis、MinIO 的真实集成测试（`make test-integration`）。
- 未重跑 Playwright 模拟 E2E；`self-test-repair-2026-10-29.md` 记录的"测试进程未正常退出"仍未复验。
- 迁移 `20261029_0083` 仅在 SQLite 上验证升降级，未在真实 PostgreSQL 执行。
- 未进行真实云端同步、真机 Android/iOS、真实 LLM 验收。
- 未提交、未推送。
