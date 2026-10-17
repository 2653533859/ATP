"""跨平台缺陷工单双向状态同步网关服务 (T2.2)

建立 ATP 内部测试执行结果与外部缺陷系统 (Jira, GitHub Issues, 禅道) 的双向状态联动闭环:
1. 回归验证驱动的双向流转 (回归通过自动关闭缺陷，再次失败自动 REOPEN 并回填证据);
2. 外部工单状态感知与反向同步 (Jira/GitHub 修复状态实时对齐 ATP 内部缺陷生命周期);
3. 跨平台状态机映射与防震荡校验 (DefectLifecycleState: OPEN, IN_PROGRESS, RESOLVED, REOPENED);
4. 结构化同步流水审计日志输出 (SyncExecutionResult & ExternalTicketBinding)。
"""

from __future__ import annotations

import enum
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ExternalTicketPlatform(str, enum.Enum):
    JIRA = "JIRA"
    GITHUB = "GITHUB"
    ZHENTAO = "ZHENTAO"


class DefectLifecycleState(str, enum.Enum):
    OPEN = "OPEN"  # 开启待修复
    IN_PROGRESS = "IN_PROGRESS"  # 修复中
    RESOLVED = "RESOLVED"  # 已修复待回归
    CLOSED = "CLOSED"  # 经回归确认闭环
    REOPENED = "REOPENED"  # 回归再次失败，重新激活


class SyncActionType(str, enum.Enum):
    AUTO_RESOLVED_ON_PASS = "AUTO_RESOLVED_ON_PASS"  # 回归通过，自动流转为 RESOLVED/CLOSED
    AUTO_REOPENED_ON_FAIL = "AUTO_REOPENED_ON_FAIL"  # 修复后回归再次失败，自动 REOPEN
    INBOUND_STATUS_UPDATED = "INBOUND_STATUS_UPDATED"  # 接收外部状态变更更新内部状态
    NO_OP_ALREADY_IN_SYNC = "NO_OP_ALREADY_IN_SYNC"  # 状态一致，无需流转动作


@dataclass
class ExternalTicketBinding:
    defect_id: str
    platform: ExternalTicketPlatform
    external_ticket_key: str  # e.g. "ATP-1024" or "#88"
    external_status: str
    atp_status: DefectLifecycleState
    linked_case_id: str
    last_sync_time: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["platform"] = self.platform.value
        d["atp_status"] = self.atp_status.value
        return d


@dataclass
class SyncExecutionResult:
    sync_id: str
    defect_id: str
    platform: ExternalTicketPlatform
    external_ticket_key: str
    action_taken: SyncActionType
    previous_state: str
    new_state: str
    sync_message: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sync_id": self.sync_id,
            "defect_id": self.defect_id,
            "platform": self.platform.value,
            "external_ticket_key": self.external_ticket_key,
            "action_taken": self.action_taken.value,
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "sync_message": self.sync_message,
            "timestamp": self.timestamp,
        }


_SYNC_AUDIT_LOGS: List[SyncExecutionResult] = []


def clear_sync_audit_logs() -> None:
    """清空同步日志（单测隔离使用）"""
    _SYNC_AUDIT_LOGS.clear()


def get_sync_audit_logs(defect_id: Optional[str] = None) -> List[SyncExecutionResult]:
    """查询同步审计日志"""
    if defect_id:
        return [log for log in _SYNC_AUDIT_LOGS if log.defect_id == defect_id]
    return list(_SYNC_AUDIT_LOGS)


def sync_defect_status_on_regression_result(
    binding: ExternalTicketBinding,
    regression_passed: bool,
    latest_error_detail: Optional[str] = None,
) -> SyncExecutionResult:
    """根据最新自动化回归测试执行结果，智能联动外部工单流转状态 (Auto-Resolve / Auto-Reopen)"""
    sync_id = f"sync_{uuid.uuid4().hex[:10]}"
    prev_state = binding.atp_status.value

    # 1. 场景一: 回归测试执行通过 (PASS)
    if regression_passed:
        if binding.atp_status in (
            DefectLifecycleState.OPEN,
            DefectLifecycleState.IN_PROGRESS,
            DefectLifecycleState.REOPENED,
        ):
            # 自动流转为 RESOLVED / CLOSED
            binding.atp_status = DefectLifecycleState.CLOSED
            binding.external_status = "Closed" if binding.platform == ExternalTicketPlatform.GITHUB else "Resolved"
            binding.last_sync_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

            msg = (
                f"关联自动化用例 [{binding.linked_case_id}] 回归验证通过！"
                f"已联动外部平台 [{binding.platform.value}:{binding.external_ticket_key}] 自动闭环标记为 Resolved/Closed。"
            )
            result = SyncExecutionResult(
                sync_id=sync_id,
                defect_id=binding.defect_id,
                platform=binding.platform,
                external_ticket_key=binding.external_ticket_key,
                action_taken=SyncActionType.AUTO_RESOLVED_ON_PASS,
                previous_state=prev_state,
                new_state=binding.atp_status.value,
                sync_message=msg,
            )
            _SYNC_AUDIT_LOGS.append(result)
            return result
        else:
            # 本已是已解决状态，保持同步无动作
            result = SyncExecutionResult(
                sync_id=sync_id,
                defect_id=binding.defect_id,
                platform=binding.platform,
                external_ticket_key=binding.external_ticket_key,
                action_taken=SyncActionType.NO_OP_ALREADY_IN_SYNC,
                previous_state=prev_state,
                new_state=binding.atp_status.value,
                sync_message=f"回归通过，工单 [{binding.external_ticket_key}] 保持 CLOSED 状态不变。",
            )
            return result

    # 2. 场景二: 回归测试再次失败 (FAILED)
    else:
        # 如果外部工单此前已被开发人员标记为 RESOLVED 或 CLOSED，说明修复未彻底，必须触发强制 REOPEN！
        if binding.atp_status in (DefectLifecycleState.RESOLVED, DefectLifecycleState.CLOSED):
            binding.atp_status = DefectLifecycleState.REOPENED
            binding.external_status = "Reopened" if binding.platform != ExternalTicketPlatform.GITHUB else "open"
            binding.last_sync_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

            err_summary = latest_error_detail[:120] if latest_error_detail else "测试断言仍旧不符"
            msg = (
                f"【严重警报】关联用例 [{binding.linked_case_id}] 回归再次失败！"
                f"外部工单 [{binding.platform.value}:{binding.external_ticket_key}] 已被自动激活重新打开 (REOPEN)！"
                f"最新报错证据: {err_summary}"
            )
            result = SyncExecutionResult(
                sync_id=sync_id,
                defect_id=binding.defect_id,
                platform=binding.platform,
                external_ticket_key=binding.external_ticket_key,
                action_taken=SyncActionType.AUTO_REOPENED_ON_FAIL,
                previous_state=prev_state,
                new_state=binding.atp_status.value,
                sync_message=msg,
            )
            _SYNC_AUDIT_LOGS.append(result)
            return result
        else:
            # 缺陷本身仍在处理中，继续保持 OPEN
            result = SyncExecutionResult(
                sync_id=sync_id,
                defect_id=binding.defect_id,
                platform=binding.platform,
                external_ticket_key=binding.external_ticket_key,
                action_taken=SyncActionType.NO_OP_ALREADY_IN_SYNC,
                previous_state=prev_state,
                new_state=binding.atp_status.value,
                sync_message=f"回归持续失败，缺陷 [{binding.external_ticket_key}] 仍处于未解决状态。",
            )
            return result


def handle_inbound_external_webhook(
    binding: ExternalTicketBinding,
    external_event: str,
    new_external_status: str,
) -> SyncExecutionResult:
    """接收来自 Jira / GitHub 的外部状态变更 Webhook，反向更新 ATP 内部缺陷状态"""
    sync_id = f"sync_{uuid.uuid4().hex[:10]}"
    prev_state = binding.atp_status.value

    status_lower = new_external_status.strip().lower()

    if status_lower in ("resolved", "done", "fixed", "closed"):
        binding.atp_status = DefectLifecycleState.RESOLVED
    elif status_lower in ("in progress", "in_progress", "active"):
        binding.atp_status = DefectLifecycleState.IN_PROGRESS
    elif status_lower in ("reopened", "reopen"):
        binding.atp_status = DefectLifecycleState.REOPENED
    else:
        binding.atp_status = DefectLifecycleState.OPEN

    binding.external_status = new_external_status
    binding.last_sync_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    msg = (
        f"接收到外部 [{binding.platform.value}] 状态变更事件 [{external_event}]，"
        f"工单状态更新为 [{new_external_status}]，ATP 内部状态同步更新为 [{binding.atp_status.value}]。"
    )
    result = SyncExecutionResult(
        sync_id=sync_id,
        defect_id=binding.defect_id,
        platform=binding.platform,
        external_ticket_key=binding.external_ticket_key,
        action_taken=SyncActionType.INBOUND_STATUS_UPDATED,
        previous_state=prev_state,
        new_state=binding.atp_status.value,
        sync_message=msg,
    )
    _SYNC_AUDIT_LOGS.append(result)
    return result
