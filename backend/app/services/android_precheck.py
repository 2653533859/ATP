"""Android 设备级执行前预检服务。

对选定设备检查在线/租约、应用映射、平台支持、定位器、变量及 Android 执行环境。
返回步骤级与设备级预检结果（步骤 ID、错误码、可修复提示）。
预检本身不操作业务 App。
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.apk import Apk
from app.models.case import TestCase
from app.models.device import Device, DeviceLease, DeviceStatus
from app.models.environment import Environment, EnvVariable
from app.models.ios import IosDevice
from app.models.project import Module
from app.schemas.android_precheck import (
    AndroidPrecheckResponse,
    AndroidPrecheckSummary,
    PrecheckItem,
    PrecheckScope,
    PrecheckStatus,
)
from app.core.encryption import decrypt_env_vars

logger = logging.getLogger(__name__)

VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")

_SUPPORTED_ACTIONS = {
    "click",
    "long_click",
    "swipe",
    "input",
    "press_key",
    "screenshot",
    "assert_text",
    "assert_element",
    "assert_visual_element",
    "wait",
    "start_app",
    "stop_app",
    "rotate",
    "grant_permission",
    "revoke_permission",
    "network_profile",
    "background",
    "foreground",
}


def _extract_variables_from_value(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, str):
        for match in VAR_PATTERN.finditer(value):
            found.add(match.group(1))
    elif isinstance(value, dict):
        for v in value.values():
            found.update(_extract_variables_from_value(v))
    elif isinstance(value, list):
        for item in value:
            found.update(_extract_variables_from_value(item))
    return found


def _check_adb_environment_state(serial: str) -> tuple[bool, str | None]:
    """安全检查 ADB 设备连通状态，不执行应用业务操作。"""
    if not shutil.which("adb"):
        return False, "ADB_UNAVAILABLE"
    try:
        proc = subprocess.run(
            ["adb", "-s", serial, "get-state"],
            capture_output=True,
            timeout=5,
            text=True,
        )
        output = (proc.stdout or "").strip().lower() + (proc.stderr or "").strip().lower()
        if proc.returncode != 0:
            if "unauthorized" in output:
                return False, "DEVICE_UNAUTHORIZED"
            if "offline" in output:
                return False, "DEVICE_OFFLINE"
            return False, "DEVICE_ADB_ERROR"
        if "device" in output:
            return True, None
        if "unauthorized" in output:
            return False, "DEVICE_UNAUTHORIZED"
        if "offline" in output:
            return False, "DEVICE_OFFLINE"
        return False, "DEVICE_ADB_ERROR"
    except subprocess.TimeoutExpired:
        return False, "DEVICE_ADB_TIMEOUT"
    except (OSError, ValueError, subprocess.SubprocessError):
        logger.exception("ADB get-state failed for %s", serial)
        return False, "DEVICE_ADB_ERROR"


async def precheck_android_execution(
    db: AsyncSession,
    *,
    case: TestCase | None = None,
    device_serial: str | None = None,
    config: dict[str, Any] | None = None,
    steps: list[dict[str, Any]] | None = None,
    extra_vars: dict[str, Any] | None = None,
    env_id: int | None = None,
    project_id: int | None = None,
    ignore_lease_owner_id: int | None = None,
    ignore_lease_token: str | None = None,
    check_adb_environment: bool = True,
    strict_adb_environment: bool = False,
) -> AndroidPrecheckResponse:
    """对 Android 用例与选定设备进行执行前诊断。"""
    items: list[PrecheckItem] = []
    if case is not None and project_id is None and getattr(case, "module_id", None):
        module = await db.get(Module, case.module_id)
        project_id = module.project_id if module else None

    # 1. 配置合并
    merged_cfg: dict[str, Any] = {}
    if case and case.config:
        merged_cfg.update(case.config)
    if config:
        merged_cfg.update(config)

    # 步骤解析
    resolved_steps: list[dict[str, Any]]
    if steps is not None:
        resolved_steps = [s if isinstance(s, dict) else {} for s in steps]
    elif "steps" in merged_cfg and isinstance(merged_cfg["steps"], list):
        resolved_steps = [s if isinstance(s, dict) else {} for s in merged_cfg["steps"]]
    else:
        resolved_steps = []

    # 目标设备序列号
    target_serial = (
        device_serial
        or merged_cfg.get("device_serial")
        or (case.config.get("device_serial") if case and case.config else None)
    )
    target_serial = str(target_serial).strip() if target_serial else None

    # 2. 设备与平台诊断
    device: Device | None = None
    if not target_serial:
        items.append(
            PrecheckItem(
                scope=PrecheckScope.device,
                status=PrecheckStatus.FAIL,
                code="MISSING_DEVICE_SERIAL",
                message="未指定 Android 目标设备序列号",
                suggestion="请在用例配置或预检请求中选择目标 Android 设备",
            )
        )
    else:
        dev_res = await db.execute(select(Device).where(Device.serial == target_serial))
        device = dev_res.scalar_one_or_none()

        if device is None:
            # 检查是否误选了 iOS 设备
            ios_res = await db.execute(select(IosDevice).where(IosDevice.udid == target_serial))
            ios_device = ios_res.scalar_one_or_none()
            if ios_device is not None:
                items.append(
                    PrecheckItem(
                        scope=PrecheckScope.platform,
                        status=PrecheckStatus.FAIL,
                        code="UNSUPPORTED_PLATFORM",
                        message=f"设备 {target_serial} 为 iOS 平台设备，Android 低代码用例不支持在该设备上执行",
                        suggestion="请选择已注册且在线的 Android 设备",
                    )
                )
            else:
                items.append(
                    PrecheckItem(
                        scope=PrecheckScope.device,
                        status=PrecheckStatus.FAIL,
                        code="DEVICE_NOT_FOUND",
                        message=f"未找到序列号为 {target_serial} 的已注册设备",
                        suggestion="设备未在平台登记，请前往「设备管理」扫描并添加该设备",
                    )
                )
        else:
            # 设备在线状态
            if device.status == DeviceStatus.offline:
                items.append(
                    PrecheckItem(
                        scope=PrecheckScope.device,
                        status=PrecheckStatus.FAIL,
                        code="DEVICE_OFFLINE",
                        message=f"设备 {target_serial} 当前处于离线状态",
                        suggestion="请检查设备 USB 或局域网连接，并确认已开启开发者选项与 USB 调试",
                    )
                )

            # 设备租约检查
            lease_res = await db.execute(select(DeviceLease).where(DeviceLease.device_id == device.id))
            lease = lease_res.scalar_one_or_none()
            now = datetime.now(timezone.utc)
            if lease is not None and lease.expires_at > now:
                is_mine = False
                if ignore_lease_token and lease.lease_token == ignore_lease_token:
                    is_mine = True
                elif ignore_lease_owner_id is not None and lease.owner_id == ignore_lease_owner_id:
                    is_mine = True

                if not is_mine:
                    expires_str = lease.expires_at.strftime("%Y-%m-%d %H:%M:%S")
                    items.append(
                        PrecheckItem(
                            scope=PrecheckScope.device,
                            status=PrecheckStatus.FAIL,
                            code="DEVICE_LEASE_CONFLICT",
                            message=f"设备 {target_serial} 当前已被任务 [{lease.owner_label}] 占用",
                            suggestion=f"请等待前序任务完成（租约预计至 {expires_str} 到期），或由任务发起人/管理员释放租约",
                        )
                    )

            # 环境层 ADB 状态检查（不操作业务 App）
            if check_adb_environment and device.status != DeviceStatus.offline:
                adb_ok, adb_code = await asyncio.to_thread(_check_adb_environment_state, target_serial)
                if not adb_ok:
                    if adb_code in {"ADB_UNAVAILABLE", "DEVICE_ADB_TIMEOUT", "DEVICE_ADB_ERROR"}:
                        items.append(
                            PrecheckItem(
                                scope=PrecheckScope.environment,
                                status=PrecheckStatus.FAIL if strict_adb_environment else PrecheckStatus.WARNING,
                                code=adb_code or "DEVICE_ADB_ERROR",
                                message=f"无法确认设备 {target_serial} 的 ADB 连通状态",
                                suggestion="请检查执行环境是否安装 adb，且设备已连接并授权 USB 调试",
                            )
                        )
                    if adb_code == "DEVICE_UNAUTHORIZED":
                        items.append(
                            PrecheckItem(
                                scope=PrecheckScope.environment,
                                status=PrecheckStatus.FAIL,
                                code="DEVICE_UNAUTHORIZED",
                                message=f"设备 {target_serial} 未获得 USB 调试授权",
                                suggestion="请点亮设备屏幕并在弹出的“允许 USB 调试”对话框中勾选允许",
                            )
                        )
                    elif adb_code == "DEVICE_OFFLINE":
                        items.append(
                            PrecheckItem(
                                scope=PrecheckScope.environment,
                                status=PrecheckStatus.FAIL,
                                code="DEVICE_OFFLINE",
                                message=f"ADB 通讯显示设备 {target_serial} 处于 offline 状态",
                                suggestion="请尝试重新插拔 USB 数据线或重启设备的 adbd 服务",
                            )
                        )

    # 3. 应用映射与包名诊断
    apk_id = merged_cfg.get("apk_id")
    if apk_id is not None:
        try:
            apk_id_int = int(apk_id)
            apk_res = await db.execute(select(Apk).where(Apk.id == apk_id_int))
            apk = apk_res.scalar_one_or_none()
            if apk is None:
                items.append(
                    PrecheckItem(
                        scope=PrecheckScope.app,
                        status=PrecheckStatus.FAIL,
                        code="APK_NOT_FOUND",
                        message=f"关联的安装包 (ID: {apk_id_int}) 不存在",
                        suggestion="请在用例配置中重新选择有效 APK，或在安装包列表中重新上传",
                    )
                )
            else:
                if project_id is not None and apk.project_id != project_id:
                    apk_name = getattr(apk, "filename", str(apk.id))
                    items.append(
                        PrecheckItem(
                            scope=PrecheckScope.app,
                            status=PrecheckStatus.FAIL,
                            code="APK_PROJECT_MISMATCH",
                            message=f"安装包 {apk_name} 所属项目 (ID: {apk.project_id}) 与当前项目不匹配",
                            suggestion="请选择属于当前项目的安装包",
                        )
                    )
        except (ValueError, TypeError):
            items.append(
                PrecheckItem(
                    scope=PrecheckScope.app,
                    status=PrecheckStatus.FAIL,
                    code="INVALID_APK_ID",
                    message=f"无效的 APK ID 格式: {apk_id}",
                    suggestion="请重新在用例配置中绑定安装包",
                )
            )

    # 执行器的应用控制动作只读取步骤 params.package，不会继承用例级 app_package。
    app_control_actions = {"start_app", "stop_app", "foreground", "grant_permission", "revoke_permission"}

    # 4. 变量定义诊断
    available_vars: set[str] = {"DEVICE_SERIAL"}
    if extra_vars:
        available_vars.update(str(k) for k in extra_vars.keys())

    if env_id is not None:
        env = await db.get(Environment, env_id)
        if env is None or (project_id is not None and env.project_id != project_id):
            items.append(
                PrecheckItem(
                    scope=PrecheckScope.environment,
                    status=PrecheckStatus.FAIL,
                    code="INVALID_ENVIRONMENT",
                    message="环境不存在或不属于当前项目",
                    suggestion="请选择当前项目下的有效环境",
                )
            )
        else:
            env_vars_res = await db.execute(select(EnvVariable).where(EnvVariable.env_id == env_id))
            decrypted_vars = decrypt_env_vars(env_vars_res.scalars().all())
            available_vars.update(decrypted_vars.keys())

    # 扫描步骤中的 {{VAR}}
    for idx, step in enumerate(resolved_steps, start=1):
        step_id = str(step.get("id") or idx)
        step_action = step.get("action")
        step_vars = _extract_variables_from_value(step)
        undefined = [v for v in sorted(step_vars) if v not in available_vars]
        for var_name in undefined:
            items.append(
                PrecheckItem(
                    scope=PrecheckScope.variable,
                    status=PrecheckStatus.WARNING,
                    code="UNDEFINED_VARIABLE",
                    step_index=idx,
                    step_id=step_id,
                    step_action=step_action,
                    message=f"步骤 {idx} [{step.get('name', '')}] 引用了未在运行变量或环境中声明的变量: {{{{{var_name}}}}}",
                    suggestion=f"请在所属环境配置变量 {var_name}，或在执行参数 extra_vars 中提供该变量值",
                )
            )

    # 5. 步骤与定位器诊断
    if not resolved_steps:
        items.append(
            PrecheckItem(
                scope=PrecheckScope.step,
                status=PrecheckStatus.FAIL,
                code="EMPTY_STEPS",
                message="用例未配置任何低代码步骤",
                suggestion="请添加至少一个低代码步骤后再进行预检或执行",
            )
        )

    for idx, step in enumerate(resolved_steps, start=1):
        step_id = str(step.get("id") or idx)
        action_raw = step.get("action")
        action = str(action_raw or "").strip().lower()
        name = step.get("name") or f"步骤 {idx}"
        params = step.get("params") or {}
        if not isinstance(params, dict):
            params = {}

        if not action or action not in _SUPPORTED_ACTIONS:
            items.append(
                PrecheckItem(
                    scope=PrecheckScope.step,
                    status=PrecheckStatus.FAIL,
                    code="UNSUPPORTED_ACTION",
                    step_index=idx,
                    step_id=step_id,
                    step_action=action or "unknown",
                    message=f"步骤 {idx} [{name}] 使用了不支持的操作类型: {action_raw}",
                    suggestion="请修改步骤操作类型为系统支持的操作（如 click, swipe, input, press_key, wait, assert_text 等）",
                )
            )
            continue

        if action == "click":
            res_id = params.get("resourceId") or params.get("resource_id")
            text = params.get("text")
            desc = params.get("contentDesc") or params.get("content_desc")
            xpath = params.get("xpath")
            has_coords = params.get("x") is not None and params.get("y") is not None
            if not (res_id or text or desc or xpath or has_coords):
                items.append(
                    PrecheckItem(
                        scope=PrecheckScope.step,
                        status=PrecheckStatus.FAIL,
                        code="MISSING_LOCATOR",
                        step_index=idx,
                        step_id=step_id,
                        step_action=action,
                        message=f"步骤 {idx} [{name}] 缺少点击定位参数",
                        suggestion="请配置 text、resourceId、contentDesc、xpath 或点击坐标 (x, y)",
                    )
                )

        elif action == "long_click":
            res_id = params.get("resourceId") or params.get("resource_id")
            text = params.get("text")
            desc = params.get("contentDesc") or params.get("content_desc")
            xpath = params.get("xpath")
            has_coords = params.get("x") is not None and params.get("y") is not None
            if not (res_id or text or desc or xpath or has_coords):
                items.append(
                    PrecheckItem(
                        scope=PrecheckScope.step,
                        status=PrecheckStatus.FAIL,
                        code="MISSING_LOCATOR",
                        step_index=idx,
                        step_id=step_id,
                        step_action=action,
                        message=f"步骤 {idx} [{name}] 缺少长按定位参数",
                        suggestion="请配置定位属性或长按坐标 (x, y)",
                    )
                )

        elif action == "swipe":
            direction = params.get("direction")
            coords = [params.get(k) for k in ("x1", "y1", "x2", "y2")]
            alt_coords = [params.get(k) for k in ("startX", "startY", "endX", "endY")]
            has_coords = all(v is not None for v in coords) or all(v is not None for v in alt_coords)
            if direction:
                if str(direction).lower() not in {"up", "down", "left", "right"}:
                    items.append(
                        PrecheckItem(
                            scope=PrecheckScope.step,
                            status=PrecheckStatus.FAIL,
                            code="INVALID_SWIPE_DIRECTION",
                            step_index=idx,
                            step_id=step_id,
                            step_action=action,
                            message=f"步骤 {idx} [{name}] 滑动方向无效: {direction}",
                            suggestion="滑动方向仅支持 up、down、left、right",
                        )
                    )
            elif not has_coords:
                items.append(
                    PrecheckItem(
                        scope=PrecheckScope.step,
                        status=PrecheckStatus.FAIL,
                        code="MISSING_LOCATOR",
                        step_index=idx,
                        step_id=step_id,
                        step_action=action,
                        message=f"步骤 {idx} [{name}] 缺少滑动参数",
                        suggestion="请配置有效 direction (up/down/left/right) 或完整的滑动起止坐标 (x1, y1, x2, y2)",
                    )
                )

        elif action == "input":
            val = params.get("text") if "text" in params else params.get("value")
            if val is None:
                items.append(
                    PrecheckItem(
                        scope=PrecheckScope.step,
                        status=PrecheckStatus.FAIL,
                        code="MISSING_INPUT_CONTENT",
                        step_index=idx,
                        step_id=step_id,
                        step_action=action,
                        message=f"步骤 {idx} [{name}] 缺少输入文本内容",
                        suggestion="请在步骤参数中填写 text 或 value 字段",
                    )
                )

        elif action == "press_key":
            key = params.get("key")
            if not key or not str(key).strip():
                items.append(
                    PrecheckItem(
                        scope=PrecheckScope.step,
                        status=PrecheckStatus.FAIL,
                        code="MISSING_KEY",
                        step_index=idx,
                        step_id=step_id,
                        step_action=action,
                        message=f"步骤 {idx} [{name}] 缺少按键名称",
                        suggestion="请在步骤参数中指定 key (如 HOME, BACK, ENTER 等)",
                    )
                )

        elif action in {"start_app", "stop_app", "foreground"}:
            pkg = params.get("package")
            if not pkg or not str(pkg).strip():
                items.append(
                    PrecheckItem(
                        scope=PrecheckScope.step,
                        status=PrecheckStatus.FAIL,
                        code="MISSING_PACKAGE",
                        step_index=idx,
                        step_id=step_id,
                        step_action=action,
                        message=f"步骤 {idx} [{name}] 缺少目标应用包名",
                        suggestion="请在步骤参数中指定 package；执行器不会继承用例级包名",
                    )
                )

        elif action in {"grant_permission", "revoke_permission"}:
            pkg = params.get("package")
            perm = params.get("permission")
            if not pkg or not perm:
                items.append(
                    PrecheckItem(
                        scope=PrecheckScope.step,
                        status=PrecheckStatus.FAIL,
                        code="MISSING_PERMISSION_PARAMS",
                        step_index=idx,
                        step_id=step_id,
                        step_action=action,
                        message=f"步骤 {idx} [{name}] 权限操作缺少 package 或 permission",
                        suggestion="请指定 package 和 permission",
                    )
                )

        elif action == "rotate":
            ori = str(params.get("orientation", "portrait")).lower()
            if ori not in {"portrait", "landscape", "reverse_portrait", "reverse_landscape"}:
                items.append(
                    PrecheckItem(
                        scope=PrecheckScope.step,
                        status=PrecheckStatus.FAIL,
                        code="INVALID_ORIENTATION",
                        step_index=idx,
                        step_id=step_id,
                        step_action=action,
                        message=f"步骤 {idx} [{name}] 屏幕方向未知: {ori}",
                        suggestion="屏幕方向仅支持 portrait、landscape、reverse_portrait、reverse_landscape",
                    )
                )

        elif action == "network_profile":
            prof = str(params.get("profile", "normal")).lower()
            if prof not in {"normal", "wifi_off", "data_off", "offline"}:
                items.append(
                    PrecheckItem(
                        scope=PrecheckScope.step,
                        status=PrecheckStatus.FAIL,
                        code="INVALID_NETWORK_PROFILE",
                        step_index=idx,
                        step_id=step_id,
                        step_action=action,
                        message=f"步骤 {idx} [{name}] 网络配置未知: {prof}",
                        suggestion="网络配置仅支持 normal、wifi_off、data_off、offline",
                    )
                )

        elif action == "assert_text":
            txt = params.get("text")
            if txt is None or not str(txt).strip():
                items.append(
                    PrecheckItem(
                        scope=PrecheckScope.step,
                        status=PrecheckStatus.FAIL,
                        code="MISSING_ASSERT_TEXT",
                        step_index=idx,
                        step_id=step_id,
                        step_action=action,
                        message=f"步骤 {idx} [{name}] 文本断言缺少预期文本",
                        suggestion="请在步骤参数中指定预期文本 text",
                    )
                )

        elif action == "assert_element":
            res = params.get("resourceId") or params.get("resource_id")
            if not res or not str(res).strip():
                items.append(
                    PrecheckItem(
                        scope=PrecheckScope.step,
                        status=PrecheckStatus.FAIL,
                        code="MISSING_ASSERT_ELEMENT",
                        step_index=idx,
                        step_id=step_id,
                        step_action=action,
                        message=f"步骤 {idx} [{name}] 元素断言缺少 resourceId",
                        suggestion="请在步骤参数中指定 resourceId",
                    )
                )

        elif action == "assert_visual_element":
            expected_text = params.get("expected_text") or params.get("text")
            image_template = params.get("image_template") or params.get("template_image")
            if not expected_text and not image_template:
                items.append(
                    PrecheckItem(
                        scope=PrecheckScope.step,
                        status=PrecheckStatus.FAIL,
                        code="MISSING_VISUAL_PARAMS",
                        step_index=idx,
                        step_id=step_id,
                        step_action=action,
                        message=f"步骤 {idx} [{name}] 视觉断言缺少预期文本或图像模板",
                        suggestion="请配置 expected_text 或 image_template",
                    )
                )

    # 6. 统计与汇总
    total_steps = len(resolved_steps)
    step_fail_indices = {
        item.step_index for item in items if item.step_index is not None and item.status == PrecheckStatus.FAIL
    }
    step_warn_indices = {
        item.step_index for item in items if item.step_index is not None and item.status == PrecheckStatus.WARNING
    }
    failed_steps = len(step_fail_indices)
    warning_steps = len(step_warn_indices - step_fail_indices)
    passed_steps = max(0, total_steps - failed_steps)
    has_blocking_issue = any(item.status == PrecheckStatus.FAIL for item in items)
    ok = not has_blocking_issue and total_steps > 0

    summary = AndroidPrecheckSummary(
        total_steps=total_steps,
        passed_steps=passed_steps,
        failed_steps=failed_steps,
        warning_steps=warning_steps,
        has_blocking_issue=has_blocking_issue,
    )

    return AndroidPrecheckResponse(
        ok=ok,
        device_serial=target_serial,
        platform="android",
        summary=summary,
        items=items,
    )
