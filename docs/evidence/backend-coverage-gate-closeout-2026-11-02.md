# 后端覆盖率门禁收口与全量套件绿灯实测报告（2026-11-02）

执行环境：Windows 本地（仓库 `E:\csh\MyProject\ATP`，Python 3.12 venv `backend/.venv`，pytest 9.0.3）。
命令与 ci.yml / Makefile 保持同范围（排除 `backend/tests/integration`）。

## 一、背景

Linux CI 运行 41427074682（commit `a030484a`，2026-11-02 手动触发）在 `Backend pytest` job 失败，唯一失败原因为覆盖率门禁：`ERROR: Coverage failure: total of 78 is less than fail-under=82`（该次实测 `3118 passed, 4 skipped`，`Total coverage: 78.22%`）；同次运行的 Backend lint、空库迁移、前端 type-check + build、Windows pytest 均通过。本轮补齐缺口测试（本地 4082 通过）并修复全量套件中的顺序依赖/环境依赖失败，使 CI 同款命令在本地一次通过，覆盖率提升至 87.08%。

## 二、全量门禁实测（CI 同款）

命令：

```bash
backend/.venv/Scripts/python.exe -m pytest backend/tests -q --ignore=backend/tests/integration \
  --cov=backend/app --cov-report=term-missing:skip-covered --cov-fail-under=82
```

实测结果：

- exit code 0；`4082 passed, 2 skipped, 1 warning in 163.45s (0:02:43)`
- `Required test coverage of 82% reached. Total coverage: 87.08%`（TOTAL 40987 语句、4283 未覆盖）
- 唯一 warning 为第三方 `StarletteDeprecationWarning`（httpx + starlette testclient），不阻断
- 覆盖率 JSON 与完整日志留存于本机作业目录（`cov_final3.json` / `full_final3.log`）

## 三、修复的 4 个门禁失败（均为测试自身问题）

### 3.1 notifier 桩泄漏（2 例，`backend/tests/worker/test_performance_coverage_gaps_worker.py`）

- 根因：`backend/tests/api/test_notifications.py` 三处裸赋值 `sys.modules["app.services.notifier"] = SimpleNamespace(...)` 不还原；worker 性能测试在函数内晚导入 `from app.services.notifier import send_notifications`，拿到残缺桩报 `AttributeError`。
- 修法：抽出 `_stub_notifier_module(monkeypatch, ...)` helper，统一改用 `monkeypatch.setitem(sys.modules, ...)`，用例结束自动还原；生产代码零改动。
- 兼容性核查：`test_notification_channel_acceptance.py`（按文件加载真实模块）、`test_dashboard_alert_internals.py`（对两种桩状态均兼容）、`test_tasks_execution_chain.py`（自带 monkeypatch.setitem 桩）均不受影响。
- 验证：三文件串联 `71 passed in 1.44s`。

### 3.2 data_dir 20GB 守卫（2 例，`backend/tests/scripts/test_windows_standalone_data_dir.py`）

- 根因：`scripts/windows-standalone.ps1` 的 `Assert-RequestedDataDir` 要求 `-DataDir` 位于剩余 ≥20GB 的本地固定盘（DriveType=3）；本机 C: 仅 ~19GB（92% 满），pytest tmp_path 落在 C: 导致 2 例失败。
- 修法：测试文件新增 `spacey_tmp_path` fixture：优先仓库盘 `.local-run`（`.gitignore` 已覆盖），否则扫描 A–Z 挑剩余最大的合格固定盘；无合格盘则 skip。生产脚本未改动。
- 验证：修复前 `2 failed, 1 passed` → 修复后 `3 passed in 3.00s`。

## 四、standalone 逐文件扫描与超时根因定位（CI 同款）

命令：`python scripts/pytest-standalone-sweep.py --jobs 4`（脚本：每文件独立子进程 + 独立 basetemp；basetemp 固定位于仓库下 `.local-run/pytest-standalone/<sha16>`，本机即 E: 盘）。

- 第一轮（并发有 mypy/lint 复核时段）：`437 passed, 2 failed`。
- 第二轮（机器空闲时段复跑）：`437 passed, 2 failed`，失败仍为 `services/test_local_schema.py`、`services/test_tunnel_hub.py`，均 `timed out after 300s`——两轮同文件复现，排除"偶然负载"，存在结构性因素。
- basetemp 时间戳取证：超时期间两个文件每个测试耗时 30–70 秒（单独快跑时 0.1–0.5 秒）且持续推进，非卡死。
- 磁盘排查：本机 C: 为 NVMe SSD（256GB）；D:、E: 为同一块 1TB 机械硬盘（ST1000DM010）的两个分区，仓库与全部 basetemp 位于 E:。fsync 基准（60×64KB 写+fsync）：E: 24.8 ms/op，C: 1.0 ms/op（约 25 倍）。
- 决定性对照实验（同一台机器、同一 4 并发形态、仅切换 basetemp 盘位）：

| 组 | basetemp 位置 | 结果 |
| --- | --- | --- |
| A′ 单进程 | E:（HDD） | `test_local_schema.py` 75s 未完成（上限 75s） |
| A 4 并发 | E:（HDD） | 两文件均 75s 超时；`test_notifications.py` 正常通过（16 passed 2.3s） |
| B 4 并发 | C:（SSD） | `test_local_schema.py` `10 passed in 4.90s`、`test_tunnel_hub.py` `99 passed in 11.27s`，全组墙钟 12.5s |

- 结论：超时根因是本机仓库盘为机械硬盘；tmp_path 重度文件（SQLite 多版本迁移、逐测试建目录）的每个测试在 HDD 上被放大到 30–70 秒，300s 上限必超。与并发、系统负载无关（单进程在 E: 上同样跑不完）。**CI 不受影响**：sweep 只在 Linux job 运行（ci.yml 第 172–173 行），runner 为 SSD；Windows CI job 不含 sweep；两个文件在 CI 同款 4 并发形态（SSD）下实测全绿。

## 五、静态门禁三件套（与 ci.yml 同范围）

| 门禁项 | 命令 | 实测结果 |
| --- | --- | --- |
| ruff check | `ruff check backend/app backend/tests <LINT_SCRIPTS>` | All checks passed |
| ruff format | `ruff format --check` 同范围 | 853 files already formatted |
| mypy | `python -m mypy`（core/schemas/services 基线） | 214 source files，0 issues |

## 六、结论

- 覆盖率 87.08% ≥ 82%，全量套件 0 失败，CI 覆盖率阻塞在本地同款命令下已消除。
- 两个门禁修复只改测试文件（净 +86/−27），生产代码零改动；ruff/format/mypy 全绿。
- standalone 扫描 439 个文件中 437 个两轮通过；仅 2 个 tmp_path 重度文件在本机 E: 机械盘上 300s 超时，对照实验证实为磁盘介质所致（同一形态换 C: SSD 后 4.90s / 11.27s 全绿），CI（SSD runner）不受影响。
- 待授权：`git commit` + `git push` 后由 GitHub CI 复跑确认（见终报"待用户授权操作"清单）。
