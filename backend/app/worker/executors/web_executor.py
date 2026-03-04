"""
Web UI 测试执行器（Playwright + pytest 脚本模式）

执行流程：
  1. 从 MinIO 下载脚本到临时目录
  2. 生成 conftest.py 注入环境变量
  3. 调用 pytest --json-report 执行
  4. 解析 pytest-json-report 结果，映射到 StepResult
  5. 收集截图（pytest-playwright 自动在失败时截图），上传 MinIO
  6. 清理临时目录
"""
import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.minio_client import download_file, upload_file, presigned_url
from app.core.redis_client import publish_run_event
from app.models.case import RunStatus, StepResult, TestCase, TestRun

logger = logging.getLogger(__name__)


async def _safe_publish(run_id: int, payload: dict) -> None:
    try:
        await publish_run_event(run_id, payload)
    except Exception:
        pass


async def run_web_case(db: AsyncSession, run: TestRun, case: TestCase, extra_vars: dict) -> None:
    cfg = case.config or {}
    script_path = cfg.get("script_path")
    if not script_path:
        run.status = RunStatus.error
        run.error_message = "用例未上传脚本文件，请先上传 .py 脚本"
        await db.commit()
        await _safe_publish(run.id, {"type": "completed", "run_id": run.id, "status": "error"})
        return

    browser = cfg.get("browser", "chromium")
    if browser != "chromium":
        logger.warning("run %s requested unsupported browser '%s', fallback to chromium", run.id, browser)
        browser = "chromium"
    headless = cfg.get("headless", True)
    viewport_width = cfg.get("viewport", {}).get("width", 1280)
    viewport_height = cfg.get("viewport", {}).get("height", 720)
    try:
        timeout_sec = int(cfg.get("timeout", 60))
    except (TypeError, ValueError):
        timeout_sec = 60
    if timeout_sec < 1:
        timeout_sec = 1

    tmpdir = Path(tempfile.mkdtemp(prefix=f"atp_run_{run.id}_"))
    total_start = time.monotonic()

    try:
        # ── 1. 下载脚本 ──────────────────────────────────────────
        local_script = tmpdir / "test_case.py"
        await asyncio.get_event_loop().run_in_executor(
            None, download_file, script_path, str(local_script)
        )

        # ── 2. 生成 conftest.py（注入环境变量 + playwright 配置）──
        env_lines = "\n".join(
            f'    os.environ[{k!r}] = {v!r}' for k, v in extra_vars.items()
        )
        conftest = tmpdir / "conftest.py"
        conftest.write_text(
            f"""import os
import pytest

@pytest.fixture(autouse=True)
def inject_env():
{env_lines or '    pass'}

@pytest.fixture(scope="session")
def browser_type_launch_args():
    return {{"headless": {str(headless)}, "args": ["--no-sandbox"]}}

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {{
        **browser_context_args,
        "viewport": {{"width": {viewport_width}, "height": {viewport_height}}},
    }}
""",
            encoding="utf-8",
        )

        # ── 3. 执行 pytest ────────────────────────────────────────
        report_file = tmpdir / "report.json"
        screenshot_dir = tmpdir / "screenshots"
        screenshot_dir.mkdir()

        cmd = [
            sys.executable, "-m", "pytest",
            str(local_script),
            f"--browser={browser}",
            "--screenshot=on",          # playwright-pytest：始终截图
            f"--output={screenshot_dir}",
            "--json-report",
            f"--json-report-file={report_file}",
            "-v",
            "--tb=short",
        ]

        env = {**os.environ, "PYTHONPATH": str(tmpdir)}
        try:
            proc = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    env=env,
                    cwd=str(tmpdir),
                    timeout=timeout_sec,
                ),
            )
        except subprocess.TimeoutExpired:
            timeout_msg = f"脚本执行超时（>{timeout_sec}秒）"
            step_result = StepResult(
                run_id=run.id,
                step_index=0,
                name="脚本执行",
                status=RunStatus.error,
                duration_ms=int((time.monotonic() - total_start) * 1000),
                error_message=timeout_msg,
            )
            db.add(step_result)
            await db.commit()
            await _safe_publish(run.id, {
                "type": "step_result",
                "run_id": run.id,
                "step": {
                    "step_index": 0,
                    "name": "脚本执行",
                    "status": RunStatus.error.value,
                    "duration_ms": step_result.duration_ms,
                    "request_data": None,
                    "response_data": None,
                    "error_message": timeout_msg,
                },
            })
            run.status = RunStatus.error
            run.error_message = timeout_msg
            run.duration_ms = step_result.duration_ms
            await db.commit()
            await _safe_publish(run.id, {"type": "completed", "run_id": run.id, "status": "error"})
            return

        # ── 4. 解析 pytest-json-report ────────────────────────────
        all_passed = True
        if report_file.exists():
            report = json.loads(report_file.read_text(encoding="utf-8"))
            tests = report.get("tests", [])
        else:
            # pytest 未能生成报告（语法错误等）
            tests = []
            all_passed = False

        # 无测试函数（脚本无 test_ 函数）
        if not tests:
            error_msg = proc.stderr or proc.stdout or "没有找到测试函数（确保函数名以 test_ 开头）"
            step_result = StepResult(
                run_id=run.id,
                step_index=0,
                name="脚本执行",
                status=RunStatus.error,
                duration_ms=int((time.monotonic() - total_start) * 1000),
                error_message=error_msg[:2000],
            )
            db.add(step_result)
            await db.commit()
            await _safe_publish(run.id, {
                "type": "step_result", "run_id": run.id,
                "step": {
                    "step_index": 0, "name": "脚本执行",
                    "status": RunStatus.error.value,
                    "duration_ms": step_result.duration_ms,
                    "request_data": None, "response_data": None,
                    "error_message": step_result.error_message,
                },
            })
            run.status = RunStatus.error
            run.error_message = error_msg[:500]
            run.duration_ms = step_result.duration_ms
            await db.commit()
            await _safe_publish(run.id, {"type": "completed", "run_id": run.id, "status": "error"})
            return

        # ── 5. 每个 test_ 函数映射为一个 StepResult ──────────────
        for idx, test in enumerate(tests):
            outcome = test.get("outcome", "failed")
            status = {
                "passed": RunStatus.passed,
                "failed": RunStatus.failed,
                "skipped": RunStatus.skipped,
            }.get(outcome, RunStatus.error)

            if status != RunStatus.passed:
                all_passed = False

            duration_ms = int(test.get("duration", 0) * 1000)
            error_message = None
            if outcome != "passed":
                call = test.get("call") or {}
                error_message = call.get("longrepr") or test.get("longrepr")
                if isinstance(error_message, dict):
                    error_message = str(error_message)

            # 收集截图（playwright-pytest 命名规则：test_name_browser.png）
            screenshot_url = None
            test_node = test.get("nodeid", "").split("::")[-1]
            for img_path in screenshot_dir.glob(f"*{test_node}*.png"):
                obj_name = f"screenshots/runs/{run.id}/step_{idx}.png"
                await asyncio.get_event_loop().run_in_executor(
                    None, upload_file, obj_name, str(img_path), "image/png"
                )
                screenshot_url = presigned_url(obj_name)
                break  # 每个测试只取第一张

            step_result = StepResult(
                run_id=run.id,
                step_index=idx,
                name=test.get("nodeid", f"test_{idx}"),
                status=status,
                duration_ms=duration_ms,
                error_message=error_message,
                screenshot_url=screenshot_url,
                response_data={"stdout": proc.stdout[-2000:] if proc.stdout else None},
            )
            db.add(step_result)
            await db.commit()

            await _safe_publish(run.id, {
                "type": "step_result", "run_id": run.id,
                "step": {
                    "step_index": idx,
                    "name": step_result.name,
                    "status": status.value,
                    "duration_ms": duration_ms,
                    "request_data": None,
                    "response_data": step_result.response_data,
                    "error_message": error_message,
                    "screenshot_url": screenshot_url,
                },
            })

    except Exception as e:
        logger.exception(f"web_executor run {run.id} error: {e}")
        all_passed = False
        run.error_message = str(e)[:500]

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    total_ms = int((time.monotonic() - total_start) * 1000)
    run.status = RunStatus.passed if all_passed else RunStatus.failed
    run.duration_ms = total_ms
    await db.commit()

    await _safe_publish(run.id, {
        "type": "completed",
        "run_id": run.id,
        "status": run.status.value,
        "duration_ms": total_ms,
    })
