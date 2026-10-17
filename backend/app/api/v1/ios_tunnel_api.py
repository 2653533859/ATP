"""iOS 设备反向 WebSocket 隧道与状态管理 API (T1.3)"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_engineer
from app.models.user import User
from app.services.ios_device_heartbeat_keeper import (
    get_heartbeat_record,
    list_heartbeat_records,
    record_ios_heartbeat,
    sweep_ios_heartbeats,
    trigger_wda_self_healing,
)
from app.services.ios_tunnel_bridge import (
    get_ios_tunnel,
    list_active_ios_tunnels,
    register_ios_tunnel,
    release_ios_tunnel,
    simulate_forward_wda_command,
)
from app.services.ios_lease_scheduler import (
    IosDeviceUnavailableError,
    IosLeaseConflictError,
    IosLeaseError,
    acquire_ios_lease,
    heartbeat_ios_lease,
    list_active_leases,
    release_ios_lease,
)
from app.services.ios_wda_session_manager import (
    capture_wda_screenshot,
    create_or_warmup_wda_session,
    dispatch_touch_gesture,
    list_wda_sessions,
    teardown_wda_session,
)
from app.services.cross_platform_device_pool_allocator import (
    allocate_matching_device,
    get_device_pool_capacity_summary,
    list_all_unified_devices,
)
from app.services.ios_crash_and_syslog_collector import (
    get_crash_report,
    get_recent_syslog,
    ingest_syslog_lines,
    list_crash_reports,
    parse_and_record_crash,
)
from app.services.ios_ipa_signing_validator import (
    list_validation_reports,
    validate_ipa_signing,
)

router = APIRouter(prefix="/ios/tunnel", tags=["iOS Tunnel"])


class RegisterIosTunnelRequest(BaseModel):
    udid: str = Field(..., description="物理 iPhone 设备唯一 UDID")
    device_name: str = Field(..., description="设备名称 (如 iPhone 15 Pro)")
    model: str = Field(..., description="内部机型标识 (如 iPhone16,1)")
    ios_version: str = Field(..., description="iOS 系统版本号 (如 17.5.1)")
    agent_id: str = Field(..., description="远端 macOS Agent 唯一标识")
    agent_name: str = Field(..., description="远端 macOS Agent 机器名称")
    remote_wda_port: int = Field(8100, description="远端 WDA 监听端口")
    preferred_local_port: Optional[int] = Field(None, description="期望分配的本地端口")


class RecordHeartbeatRequest(BaseModel):
    udid: str = Field(..., description="设备唯一 UDID")
    agent_id: str = Field(..., description="所属 Agent ID")
    battery_level: int = Field(100, ge=0, le=100, description="电池电量百分比")
    battery_charging: bool = Field(True, description="是否处于充电状态")
    temperature_celsius: float = Field(28.5, description="设备电池温度")
    wda_alive: bool = Field(True, description="WebDriverAgent 探针是否存活")


class ForwardWdaCommandRequest(BaseModel):
    udid: str = Field(..., description="目标设备 UDID")
    command_path: str = Field(..., description="WDA REST 相对路径 (如 /status 或 /screenshot)")
    method: str = Field("GET", description="HTTP 请求方法")
    params: Dict[str, Any] = Field(default_factory=dict, description="指令参数载荷")


class HealWdaRequest(BaseModel):
    udid: str = Field(..., description="目标设备 UDID")


class SweepHeartbeatsRequest(BaseModel):
    timeout_seconds: float = Field(15.0, description="心跳超时判定阈值 (秒)")


class AcquireLeaseRequest(BaseModel):
    udid: str = Field(..., description="目标物理 iPhone UDID")
    purpose: str = Field("automated_test", description="租用用途说明")
    ttl_seconds: int = Field(300, ge=30, le=1800, description="租约有效时长 (秒)")
    force_takeover: bool = Field(False, description="是否强制接管既有租约 (管理员权限)")


class HeartbeatLeaseRequest(BaseModel):
    udid: str = Field(..., description="目标设备 UDID")
    lease_token: str = Field(..., description="持有的有效租约凭据 Token")
    additional_ttl_seconds: Optional[int] = Field(None, ge=30, le=1800, description="延长的租期秒数")


class ReleaseLeaseRequest(BaseModel):
    udid: str = Field(..., description="目标设备 UDID")
    lease_token: Optional[str] = Field(None, description="持有的有效租约凭据 Token")
    admin_force: bool = Field(False, description="是否管理员特权强制释放")


class WarmupWdaSessionRequest(BaseModel):
    udid: str = Field(..., description="目标设备 UDID")
    lease_token: str = Field(..., description="有效租约凭据 Token")
    bundle_id: str = Field("com.apple.Preferences", description="前台预热 App Bundle ID")
    capabilities: Dict[str, Any] = Field(default_factory=dict, description="Session 启动参数配置")


class DispatchGestureRequest(BaseModel):
    udid: str = Field(..., description="目标设备 UDID")
    session_id: str = Field(..., description="活跃 WDA Session ID")
    action: str = Field("tap", description="手势动作类型 (tap | swipe | home)")
    x: float = Field(0.0, description="起始 X 坐标")
    y: float = Field(0.0, description="起始 Y 坐标")
    end_x: float = Field(0.0, description="结束 X 坐标 (swipe 动作)")
    end_y: float = Field(0.0, description="结束 Y 坐标 (swipe 动作)")
    duration_ms: float = Field(300.0, description="滑动耗时毫秒数")


class AllocateDeviceRequest(BaseModel):
    platform: str = Field("any", description="目标平台 (ios | android | any)")
    brand: Optional[str] = Field(None, description="机型品牌过滤")
    min_os_version: Optional[str] = Field(None, description="最低系统版本要求")
    auto_lease: bool = Field(False, description="匹配成功是否自动申请排他租约")


class IngestSyslogRequest(BaseModel):
    udid: str = Field(..., description="目标物理 iPhone UDID")
    lines: List[str] = Field(default_factory=list, description="Syslog 控制台日志行列表")


class UploadCrashReportRequest(BaseModel):
    udid: str = Field(..., description="目标物理 iPhone UDID")
    raw_crash_text: str = Field(..., description="iOS 原生 IPS / Crash 日志文本")
    run_id: Optional[str] = Field(None, description="绑定的测试运行任务 RunID")
    step_index: Optional[int] = Field(None, description="绑定的测试步骤索引")


class ValidateIpaSigningRequest(BaseModel):
    provisioning_data: Dict[str, Any] = Field(..., description="IPA embedded.mobileprovision 元数据字典")
    target_device_udid: Optional[str] = Field(None, description="拟部署目标真机 UDID")
    expected_bundle_id: Optional[str] = Field(None, description="期望的测试应用 Bundle ID")


@router.post("/register")
def register_tunnel_endpoint(
    payload: RegisterIosTunnelRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """注册一台物理 iPhone 的反向隧道并分配映射端口"""
    session = register_ios_tunnel(
        udid=payload.udid,
        device_name=payload.device_name,
        model=payload.model,
        ios_version=payload.ios_version,
        agent_id=payload.agent_id,
        agent_name=payload.agent_name,
        remote_wda_port=payload.remote_wda_port,
        preferred_local_port=payload.preferred_local_port,
    )
    # 自动关联心跳注册
    record_ios_heartbeat(
        udid=payload.udid,
        agent_id=payload.agent_id,
        wda_alive=True,
    )
    return {
        "message": f"iOS 设备 [{payload.device_name}] 反向隧道建立成功",
        "tunnel": session.to_dict(),
    }


@router.post("/heartbeat")
def heartbeat_endpoint(
    payload: RecordHeartbeatRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """接收来自 Agent 的物理 iPhone 心跳探针上报"""
    rec = record_ios_heartbeat(
        udid=payload.udid,
        agent_id=payload.agent_id,
        battery_level=payload.battery_level,
        battery_charging=payload.battery_charging,
        temperature_celsius=payload.temperature_celsius,
        wda_alive=payload.wda_alive,
    )
    return {
        "message": "心跳已更新",
        "heartbeat": rec.to_dict(),
    }


@router.get("/devices")
def list_devices_endpoint(
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """列出全部通过隧道连接的 iOS 真机设备与其心跳状态"""
    tunnels = list_active_ios_tunnels()
    heartbeats = {r["udid"]: r for r in list_heartbeat_records()}

    merged: List[Dict[str, Any]] = []
    for t in tunnels:
        item = dict(t)
        hb = heartbeats.get(t["udid"])
        item["battery_level"] = hb.get("battery_level", 100) if hb else 100
        item["temperature_celsius"] = hb.get("temperature_celsius", 28.0) if hb else 28.0
        item["wda_alive"] = hb.get("wda_alive", True) if hb else True
        item["health_status"] = hb.get("status", "ONLINE") if hb else "ONLINE"
        merged.append(item)

    return {
        "total": len(merged),
        "devices": merged,
    }


@router.get("/device/{udid}")
def get_device_endpoint(
    udid: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询单台物理 iPhone 隧道会话详情"""
    session = get_ios_tunnel(udid)
    if not session:
        raise HTTPException(status_code=404, detail="未找到目标设备的活跃反向隧道")
    hb = get_heartbeat_record(udid)
    res = session.to_dict()
    res["heartbeat"] = hb.to_dict() if hb else None
    return {"device": res}


@router.post("/wda/forward")
def forward_wda_endpoint(
    payload: ForwardWdaCommandRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """通过反向隧道向 iPhone 设备的 WDA 代理下发指令"""
    try:
        wda_res = simulate_forward_wda_command(
            udid=payload.udid,
            command_path=payload.command_path,
            method=payload.method,
            params=payload.params,
        )
        return {
            "udid": payload.udid,
            "command": payload.command_path,
            "response": wda_res,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/wda/heal")
def heal_wda_endpoint(
    payload: HealWdaRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """触发 WDA 异常自愈重启"""
    try:
        res = trigger_wda_self_healing(payload.udid)
        return res
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/sweep")
def sweep_heartbeats_endpoint(
    payload: SweepHeartbeatsRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """执行全部真机的心跳保活巡检，超时失联标记为 OFFLINE"""
    offline_udids = sweep_ios_heartbeats(timeout_seconds=payload.timeout_seconds)
    return {
        "message": f"巡检完成，共将 {len(offline_udids)} 台失联设备标记为 OFFLINE",
        "offline_udids": offline_udids,
    }


@router.delete("/{udid}")
def release_tunnel_endpoint(
    udid: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """注销并释放指定 iPhone 的反向隧道"""
    released = release_ios_tunnel(udid)
    if not released:
        raise HTTPException(status_code=404, detail="该设备隧道不存在或已被释放")
    return {"message": f"设备 [{udid}] 反向隧道已成功断开释放"}


@router.post("/lease/acquire")
def acquire_lease_endpoint(
    payload: AcquireLeaseRequest,
    user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """申请排他性独占租用一台 iPhone 设备"""
    try:
        lease = acquire_ios_lease(
            udid=payload.udid,
            owner_id=user.id,
            owner_label=user.username,
            purpose=payload.purpose,
            ttl_seconds=payload.ttl_seconds,
            force_takeover=payload.force_takeover,
        )
        return {
            "message": f"成功获得设备 [{payload.udid}] 的排他性租约",
            "lease": lease.to_dict(),
        }
    except IosLeaseConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except IosDeviceUnavailableError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/lease/heartbeat")
def lease_heartbeat_endpoint(
    payload: HeartbeatLeaseRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """为活动租约发送保活续期心跳"""
    try:
        lease = heartbeat_ios_lease(
            udid=payload.udid,
            lease_token=payload.lease_token,
            additional_ttl_seconds=payload.additional_ttl_seconds,
        )
        return {
            "message": "租约已成功续期",
            "lease": lease.to_dict(),
        }
    except IosLeaseError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/lease/release")
def release_lease_endpoint(
    payload: ReleaseLeaseRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """主动释放归还 iPhone 设备租约"""
    try:
        res = release_ios_lease(
            udid=payload.udid,
            lease_token=payload.lease_token,
            admin_force=payload.admin_force,
        )
        if not res:
            raise HTTPException(status_code=404, detail="未找到该设备的活动租约记录")
        return {"message": f"设备 [{payload.udid}] 租约已成功释放归还"}
    except IosLeaseError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/leases")
def list_leases_endpoint(
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """列出当前全部处于活动占用状态的 iOS 租约"""
    leases = list_active_leases()
    return {
        "total": len(leases),
        "leases": leases,
    }


@router.post("/wda/session/warmup")
def warmup_wda_session_endpoint(
    payload: WarmupWdaSessionRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """基于租约预热并创建 WDA 执行会话"""
    try:
        sess = create_or_warmup_wda_session(
            udid=payload.udid,
            lease_token=payload.lease_token,
            bundle_id=payload.bundle_id,
            capabilities=payload.capabilities,
        )
        return {
            "message": "WDA 会话初始化预热成功",
            "session": sess.to_dict(),
        }
    except (PermissionError, ConnectionError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/wda/sessions")
def list_wda_sessions_endpoint(
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """列出当前活跃的 WDA 会话"""
    sessions = list_wda_sessions()
    return {
        "total": len(sessions),
        "sessions": sessions,
    }


@router.delete("/wda/session/{udid}")
def teardown_wda_session_endpoint(
    udid: str,
    session_id: Optional[str] = None,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """优雅关闭 WDA 会话并清理前台环境"""
    try:
        res = teardown_wda_session(udid=udid, session_id=session_id)
        if not res:
            raise HTTPException(status_code=404, detail="未找到该设备的活跃 WDA 会话")
        return {"message": f"设备 [{udid}] 的 WDA 会话已优雅注销"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/wda/screenshot/{udid}")
def get_screenshot_endpoint(
    udid: str,
    session_id: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """获取真机当前实时屏幕快照截图"""
    try:
        img_b64 = capture_wda_screenshot(udid=udid, session_id=session_id)
        return {
            "udid": udid,
            "session_id": session_id,
            "screenshot_base64": img_b64,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/wda/gesture")
def dispatch_gesture_endpoint(
    payload: DispatchGestureRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """向目标设备下发点击、滑动或 Home 触控手势动作"""
    try:
        res = dispatch_touch_gesture(
            udid=payload.udid,
            session_id=payload.session_id,
            action=payload.action,
            x=payload.x,
            y=payload.y,
            end_x=payload.end_x,
            end_y=payload.end_y,
            duration_ms=payload.duration_ms,
        )
        return {
            "message": "手势执行成功",
            "result": res,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/pool/allocate")
def allocate_device_endpoint(
    payload: AllocateDeviceRequest,
    user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """跨端匹配最佳真机，并可选自动申请排他租约"""
    matched = allocate_matching_device(
        platform=payload.platform,
        brand=payload.brand,
        min_os_version=payload.min_os_version,
        auto_lease=payload.auto_lease,
        owner_id=user.id,
        owner_label=user.username,
    )
    if not matched:
        raise HTTPException(status_code=404, detail="未在跨端设备池中找到满足条件的可用真机")
    return {
        "message": f"成功匹配调度移动真机 [{matched['name']}]",
        "device": matched,
    }


@router.get("/pool/capacity")
def get_capacity_endpoint(
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """获取跨端移动真机池容量与负载负载统计"""
    summary = get_device_pool_capacity_summary()
    return {"capacity": summary}


@router.get("/pool/devices")
def get_all_pool_devices_endpoint(
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """列出跨端设备池所有统一设备"""
    devices = list_all_unified_devices()
    return {
        "total": len(devices),
        "devices": [d.to_dict() for d in devices],
    }


@router.post("/syslog/ingest")
def ingest_syslog_endpoint(
    payload: IngestSyslogRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """接收 Agent 上报的 iOS 系统控制台 Syslog 流"""
    count = ingest_syslog_lines(udid=payload.udid, raw_lines=payload.lines)
    return {
        "message": f"成功归档 {count} 行 Syslog",
        "udid": payload.udid,
        "ingested_lines": count,
    }


@router.get("/syslog/{udid}")
def get_syslog_endpoint(
    udid: str,
    limit: int = 100,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """获取指定真机的实时 Syslog 缓冲记录"""
    lines = get_recent_syslog(udid=udid, limit=limit)
    return {
        "total": len(lines),
        "syslog": lines,
    }


@router.post("/crash/report")
def upload_crash_endpoint(
    payload: UploadCrashReportRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """解析并归档应用闪退 Crash 报告"""
    report = parse_and_record_crash(
        udid=payload.udid,
        raw_crash_text=payload.raw_crash_text,
        run_id=payload.run_id,
        step_index=payload.step_index,
    )
    return {
        "message": "iOS 崩溃堆栈解析归档成功",
        "crash": report.to_dict(),
    }


@router.get("/crash/{crash_id}")
def get_crash_endpoint(
    crash_id: str,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询指定崩溃详情与符号化调用栈"""
    report = get_crash_report(crash_id)
    if not report:
        raise HTTPException(status_code=404, detail="未找到目标崩溃报告记录")
    return {"crash": report.to_dict()}


@router.get("/crashes")
def list_crashes_endpoint(
    udid: Optional[str] = None,
    run_id: Optional[str] = None,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """查询全量已归档的 iOS 崩溃报告"""
    reports = list_crash_reports(udid=udid, run_id=run_id)
    return {
        "total": len(reports),
        "crashes": reports,
    }


@router.post("/ipa/validate")
def validate_ipa_endpoint(
    payload: ValidateIpaSigningRequest,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """校验 IPA 签名合规性、描述文件有效期与目标真机 UDID 白名单"""
    report = validate_ipa_signing(
        provisioning_data=payload.provisioning_data,
        target_device_udid=payload.target_device_udid,
        expected_bundle_id=payload.expected_bundle_id,
    )
    return {
        "message": "IPA 签名合规校验完成",
        "report": report.to_dict(),
    }


@router.get("/ipa/validations")
def list_ipa_validations_endpoint(
    limit: int = 50,
    _user: User = Depends(require_engineer),
) -> Dict[str, Any]:
    """列出近期 IPA 签名合规校验审计历史"""
    items = list_validation_reports(limit=limit)
    return {
        "total": len(items),
        "validations": items,
    }
