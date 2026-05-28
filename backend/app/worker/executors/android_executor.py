"""
Android UI 测试执行器（uiautomator2 + pytest 脚本模式）

执行流程：
  1. 连接 ADB 设备（通过 serial）
  2. 可选：安装 APK 到设备
  3. 从 MinIO 下载脚本到临时目录
  4. 生成 conftest.py 注入设备 serial 和环境变量
  5. 调用 pytest --json-report 执行
  6. 解析 pytest-json-report 结果，映射到 StepResult
  7. 收集截图，上传 MinIO
  8. 清理临时目录
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
from app.services.adb_resilience import (
    HeartbeatMonitor,
    ensure_reachable,
    is_adb_timeout,
    safe_run_adb,
)
from app.services.ai_healing import apply_healing_hook, enqueue_diagnosis, maybe_enqueue_run_healing

logger = logging.getLogger(__name__)


async def _safe_publish(run_id: int, payload: dict) -> None:
    try:
        await publish_run_event(run_id, payload)
    except Exception:
        pass


def _install_apk(serial: str, apk_path: str, timeout: int = 120) -> tuple[bool, str]:
    """通过 adb 安装 APK 到设备，返回 (success, message)；走 safe_run_adb 自动重试一次。"""
    proc = safe_run_adb(
        serial,
        ["install", "-r", "-t", apk_path],
        timeout=timeout,
        retries=1,
    )
    if proc is None:
        return False, "adb 命令未找到，请检查 ADB 环境"
    if proc.returncode == 0 and "Success" in (proc.stdout or ""):
        return True, "APK 安装成功"
    if is_adb_timeout(proc):
        return False, f"APK 安装超时（>{timeout}秒）"
    return False, (proc.stderr or proc.stdout or "安装失败")[:500]


def _check_device_reachable(serial: str, timeout: int = 10) -> tuple[bool, str]:
    """执行前校验设备是否可达；包装 ensure_reachable 以保留旧 API。"""
    return ensure_reachable(serial, timeout=timeout)


async def run_android_case(
    db: AsyncSession,
    run: TestRun,
    case: TestCase,
    extra_vars: dict,
) -> None:
    cfg = case.config or {}
    script_path = cfg.get("script_path")
    if not script_path:
        run.status = RunStatus.error
        run.error_message = "用例未上传脚本文件，请先上传 .py 脚本"
        await db.commit()
        await _safe_publish(run.id, {"type": "completed", "run_id": run.id, "status": "error"})
        return

    device_serial = cfg.get("device_serial")
    if not device_serial:
        run.status = RunStatus.error
        run.error_message = "未选择执行设备，请在用例配置中选择设备"
        await db.commit()
        await _safe_publish(run.id, {"type": "completed", "run_id": run.id, "status": "error"})
        return

    apk_object_name = cfg.get("apk_object_name")  # MinIO path of APK
    reachable, device_message = await asyncio.get_event_loop().run_in_executor(
        None, _check_device_reachable, device_serial
    )
    if not reachable:
        run.status = RunStatus.error
        run.error_message = (
            f"Android 设备不可达：{device_message}。"
            "若使用 Docker worker 连接宿主机真机，建议先在宿主机执行 adb tcpip 5555、adb connect <device-ip>:5555，"
            "并确保 worker 与宿主机网络互通。"
        )
        await db.commit()
        await _safe_publish(run.id, {"type": "completed", "run_id": run.id, "status": "error"})
        return
    try:
        timeout_sec = int(cfg.get("timeout", 120))
    except (TypeError, ValueError):
        timeout_sec = 120
    if timeout_sec < 1:
        timeout_sec = 1

    tmpdir = Path(tempfile.mkdtemp(prefix=f"atp_android_{run.id}_"))
    total_start = time.monotonic()
    all_passed = True

    try:
        # ── 1. 可选：下载并安装 APK ─────────────────────────
        if apk_object_name:
            apk_local = tmpdir / "app.apk"
            await _safe_publish(run.id, {
                "type": "step_progress", "run_id": run.id,
                "message": "正在下载并安装 APK...",
            })
            await asyncio.get_event_loop().run_in_executor(
                None, download_file, apk_object_name, str(apk_local)
            )
            success, install_msg = await asyncio.get_event_loop().run_in_executor(
                None, _install_apk, device_serial, str(apk_local)
            )
            if not success:
                run.status = RunStatus.error
                run.error_message = f"APK 安装失败: {install_msg}"
                await db.commit()
                await _safe_publish(run.id, {"type": "completed", "run_id": run.id, "status": "error"})
                return

        # ── 2. 下载脚本 ────────────────────────────────────
        local_script = tmpdir / "test_case.py"
        await asyncio.get_event_loop().run_in_executor(
            None, download_file, script_path, str(local_script)
        )

        # ── 3. 生成 conftest.py（注入设备 serial + 环境变量）──
        env_lines = "\n".join(
            f'    os.environ[{k!r}] = {v!r}' for k, v in extra_vars.items()
        )
        conftest = tmpdir / "conftest.py"
        conftest.write_text(
            f"""import os
import pytest

@pytest.fixture(autouse=True)
def inject_env():
    os.environ["DEVICE_SERIAL"] = {device_serial!r}
{env_lines or '    pass'}

@pytest.fixture(scope="session")
def device_serial():
    return {device_serial!r}
""",
            encoding="utf-8",
        )

        # ── 4. 执行 pytest ──────────────────────────────────
        report_file = tmpdir / "report.json"
        screenshot_dir = tmpdir / "screenshots"
        screenshot_dir.mkdir()

        cmd = [
            sys.executable, "-m", "pytest",
            str(local_script),
            "--json-report",
            f"--json-report-file={report_file}",
            "-v",
            "--tb=short",
        ]

        env = {
            **os.environ,
            "PYTHONPATH": str(tmpdir),
            "DEVICE_SERIAL": device_serial,
        }

        # 心跳监控：执行期间设备掉线时立即终止 pytest 子进程
        pytest_proc: asyncio.subprocess.Process | None = None
        device_lost_msg: str | None = None
        subprocess_error_msg: str | None = None

        def _on_device_lost(reason: str) -> None:
            nonlocal device_lost_msg
            device_lost_msg = (
                f"执行中途设备 {device_serial} 失联：{reason}。"
                "心跳监控已终止 pytest 进程，请检查 USB/TCP 链路后重试。"
            )
            logger.warning("android run %s: %s", run.id, device_lost_msg)
            if pytest_proc is not None and pytest_proc.returncode is None:
                try:
                    pytest_proc.terminate()
                except Exception:
                    pass

        try:
            async with HeartbeatMonitor(device_serial, on_lost=_on_device_lost):
                pytest_proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    cwd=str(tmpdir),
                )
                try:
                    stdout_b, stderr_b = await asyncio.wait_for(
                        pytest_proc.communicate(), timeout=timeout_sec
                    )
                except asyncio.TimeoutError:
                    try:
                        pytest_proc.kill()
                    except Exception:
                        pass
                    # 收集已有输出
                    try:
                        stdout_b, stderr_b = await asyncio.wait_for(
                            pytest_proc.communicate(), timeout=5
                        )
                    except Exception:
                        stdout_b, stderr_b = b"", b""
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
                        "type": "step_result", "run_id": run.id,
                        "step": {
                            "step_index": 0, "name": "脚本执行",
                            "status": RunStatus.error.value,
                            "duration_ms": step_result.duration_ms,
                            "request_data": None, "response_data": None,
                            "error_message": timeout_msg,
                        },
                    })
                    run.status = RunStatus.error
                    run.error_message = timeout_msg
                    run.duration_ms = step_result.duration_ms
                    await db.commit()
                    await _safe_publish(run.id, {"type": "completed", "run_id": run.id, "status": "error"})
                    return
        except Exception as exec_err:
            logger.exception("android pytest subprocess error: %s", exec_err)
            subprocess_error_msg = f"pytest 子进程启动失败：{exec_err}"[:500]
            stdout_b, stderr_b = b"", str(exec_err).encode("utf-8", errors="ignore")

        # 子进程从未成功启动 → 直接以明确错误结束（避免错误信息被后续"未找到测试函数"分支掩盖）
        if pytest_proc is None or subprocess_error_msg is not None:
            err_msg = subprocess_error_msg or "pytest 子进程未能启动"
            step_result = StepResult(
                run_id=run.id,
                step_index=0,
                name="脚本执行",
                status=RunStatus.error,
                duration_ms=int((time.monotonic() - total_start) * 1000),
                error_message=err_msg,
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
                    "error_message": err_msg,
                },
            })
            run.status = RunStatus.error
            run.error_message = err_msg
            run.duration_ms = step_result.duration_ms
            await db.commit()
            await _safe_publish(run.id, {"type": "completed", "run_id": run.id, "status": "error"})
            return

        proc = subprocess.CompletedProcess(
            args=cmd,
            returncode=pytest_proc.returncode if pytest_proc.returncode is not None else -1,
            stdout=(stdout_b or b"").decode("utf-8", errors="ignore"),
            stderr=(stderr_b or b"").decode("utf-8", errors="ignore"),
        )

        # 心跳监控判定设备失联：直接以明确错误结束
        if device_lost_msg:
            step_result = StepResult(
                run_id=run.id,
                step_index=0,
                name="脚本执行",
                status=RunStatus.error,
                duration_ms=int((time.monotonic() - total_start) * 1000),
                error_message=device_lost_msg,
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
                    "error_message": device_lost_msg,
                },
            })
            run.status = RunStatus.error
            run.error_message = device_lost_msg[:500]
            run.duration_ms = step_result.duration_ms
            await db.commit()
            await _safe_publish(run.id, {"type": "completed", "run_id": run.id, "status": "error"})
            return

        # ── 5. 解析 pytest-json-report ──────────────────────
        if report_file.exists():
            report = json.loads(report_file.read_text(encoding="utf-8"))
            tests = report.get("tests", [])
        else:
            tests = []
            all_passed = False

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

        # ── 6. 每个 test_ 函数映射为 StepResult ─────────────
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

            # 收集截图（uiautomator2 脚本可在 screenshots/ 目录输出截图）
            screenshot_url = None
            test_node = test.get("nodeid", "").split("::")[-1]
            for img_path in screenshot_dir.glob(f"*{test_node}*.png"):
                obj_name = f"screenshots/runs/{run.id}/step_{idx}.png"
                await asyncio.get_event_loop().run_in_executor(
                    None, upload_file, obj_name, str(img_path), "image/png"
                )
                screenshot_url = presigned_url(obj_name)
                break
            # 也扫描 tmpdir 中可能的截图
            if not screenshot_url:
                for img_path in tmpdir.glob(f"*{test_node}*.png"):
                    obj_name = f"screenshots/runs/{run.id}/step_{idx}.png"
                    await asyncio.get_event_loop().run_in_executor(
                        None, upload_file, obj_name, str(img_path), "image/png"
                    )
                    screenshot_url = presigned_url(obj_name)
                    break

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
            needs_healing = apply_healing_hook(step_result)
            db.add(step_result)
            await db.commit()
            if needs_healing:
                enqueue_diagnosis(step_result.id)

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
        logger.exception("android_executor run %s error: %s", run.id, e)
        all_passed = False
        run.error_message = str(e)[:500]

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    total_ms = int((time.monotonic() - total_start) * 1000)
    run.status = RunStatus.passed if all_passed else RunStatus.failed
    run.duration_ms = total_ms
    await db.commit()

    # iter3 多 step 综合诊断
    await maybe_enqueue_run_healing(db, run)

    await _safe_publish(run.id, {
        "type": "completed",
        "run_id": run.id,
        "status": run.status.value,
        "duration_ms": total_ms,
    })
