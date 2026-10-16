"""Sagas/TCC 分布式事务流转跟踪与悬挂事务探测引擎 (T2.1)。

负责在多微服务协作长事务中：
1. 跟踪全局事务 (GlobalTx) 与子分支事务 (BranchTx) 的 Try / Confirm / Cancel 阶段流转；
2. 探测悬挂事务 (Hanging Transaction，如未 Try 先 Cancel 或 Cancel 先行导致 Try 悬挂)；
3. 识别空补偿 (Empty Compensation) 与超时未决 (Timeout Pending) 异常；
4. 输出分布式事务一致性审计报告与补偿修复行动建议。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any
import uuid

logger = logging.getLogger(__name__)


class TransactionPattern(str, Enum):
    TCC = "TCC"  # Try - Confirm - Cancel
    SAGA = "SAGA"  # Forward - Compensate


class GlobalTxStatus(str, Enum):
    ACTIVE = "ACTIVE"  # 进行中
    COMMITTED = "COMMITTED"  # 全部分支确认提交成功
    ROLLED_BACK = "ROLLED_BACK"  # 正常全部分支补偿回滚
    HANGING = "HANGING"  # 悬挂事务 (异常)
    INCONSISTENT = "INCONSISTENT"  # 部分成功部分失败未补偿 (数据不一致)
    TIMEOUT = "TIMEOUT"  # 超时未决


class BranchStage(str, Enum):
    TRY = "TRY"
    CONFIRM = "CONFIRM"
    CANCEL = "CANCEL"
    FORWARD = "FORWARD"
    COMPENSATE = "COMPENSATE"


class BranchStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class SagaAnomalyType(str, Enum):
    HANGING_TRANSACTION = "HANGING_TRANSACTION"  # 悬挂事务：Cancel 先于 Try 到达并被执行，Try 随后到达长期悬挂
    EMPTY_COMPENSATION = "EMPTY_COMPENSATION"  # 空补偿：未执行 Try/Forward 却收到了 Cancel/Compensate
    TIMEOUT_PENDING = "TIMEOUT_PENDING"  # 超时未决：分支长久处于 PENDING 未决状态
    PARTIAL_COMMIT_FAILURE = "PARTIAL_COMMIT_FAILURE"  # 部分提交失败导致跨服务数据撕裂
    NONE = "NONE"


@dataclass
class BranchTxRecord:
    branch_id: str
    global_tx_id: str
    service_name: str
    action_name: str
    stage: BranchStage
    status: BranchStatus
    duration_ms: float = 0.0
    error_message: str = ""
    retry_count: int = 0
    payload: dict[str, Any] = field(default_factory=dict)
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "global_tx_id": self.global_tx_id,
            "service_name": self.service_name,
            "action_name": self.action_name,
            "stage": self.stage.value,
            "status": self.status.value,
            "duration_ms": round(self.duration_ms, 2),
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "payload": self.payload,
            "recorded_at": self.recorded_at.isoformat(),
        }


@dataclass
class GlobalTxRecord:
    global_tx_id: str
    business_key: str
    pattern: TransactionPattern
    status: GlobalTxStatus
    timeout_seconds: float = 30.0
    branches: list[BranchTxRecord] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "global_tx_id": self.global_tx_id,
            "business_key": self.business_key,
            "pattern": self.pattern.value,
            "status": self.status.value,
            "timeout_seconds": self.timeout_seconds,
            "branches_count": len(self.branches),
            "branches": [b.to_dict() for b in self.branches],
            "started_at": self.started_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class SagaAuditReport:
    global_tx_id: str
    business_key: str
    pattern: TransactionPattern
    status: GlobalTxStatus
    is_consistent: bool
    detected_anomaly: SagaAnomalyType
    anomaly_description: str
    branches: list[BranchTxRecord]
    remediation_advice: list[str]
    audited_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "global_tx_id": self.global_tx_id,
            "business_key": self.business_key,
            "pattern": self.pattern.value,
            "status": self.status.value,
            "is_consistent": self.is_consistent,
            "detected_anomaly": self.detected_anomaly.value,
            "anomaly_description": self.anomaly_description,
            "branches_count": len(self.branches),
            "branches": [b.to_dict() for b in self.branches],
            "remediation_advice": self.remediation_advice,
            "audited_at": self.audited_at.isoformat(),
        }


# 全局事务存储仓库: global_tx_id -> GlobalTxRecord
_GLOBAL_TX_STORE: dict[str, GlobalTxRecord] = {}


def record_global_tx(
    global_tx_id: str | None = None,
    business_key: str = "",
    pattern: str = "TCC",
    timeout_seconds: float = 30.0,
) -> GlobalTxRecord:
    """初始化或注册全局事务。"""
    gid = global_tx_id or f"gtx_{uuid.uuid4().hex[:12]}"
    pat = (
        TransactionPattern(pattern.upper())
        if pattern.upper() in TransactionPattern._value2member_map_
        else TransactionPattern.TCC
    )

    if gid in _GLOBAL_TX_STORE:
        tx = _GLOBAL_TX_STORE[gid]
        tx.business_key = business_key or tx.business_key
        tx.updated_at = datetime.now(timezone.utc)
        return tx

    tx = GlobalTxRecord(
        global_tx_id=gid,
        business_key=business_key or f"order_{uuid.uuid4().hex[:8]}",
        pattern=pat,
        status=GlobalTxStatus.ACTIVE,
        timeout_seconds=timeout_seconds,
    )
    _GLOBAL_TX_STORE[gid] = tx
    return tx


def record_branch_tx(
    global_tx_id: str,
    service_name: str,
    action_name: str,
    stage: str = "TRY",
    status: str = "SUCCESS",
    duration_ms: float = 0.0,
    error_message: str = "",
    retry_count: int = 0,
    payload: dict[str, Any] | None = None,
    branch_id: str | None = None,
) -> BranchTxRecord:
    """记录分支事务状态并挂载到对应全局事务。"""
    tx = _GLOBAL_TX_STORE.get(global_tx_id)
    if not tx:
        tx = record_global_tx(global_tx_id=global_tx_id)

    b_stage = BranchStage(stage.upper()) if stage.upper() in BranchStage._value2member_map_ else BranchStage.TRY
    b_status = (
        BranchStatus(status.upper()) if status.upper() in BranchStatus._value2member_map_ else BranchStatus.SUCCESS
    )
    bid = branch_id or f"br_{uuid.uuid4().hex[:8]}"

    branch = BranchTxRecord(
        branch_id=bid,
        global_tx_id=global_tx_id,
        service_name=service_name,
        action_name=action_name,
        stage=b_stage,
        status=b_status,
        duration_ms=duration_ms,
        error_message=error_message,
        retry_count=retry_count,
        payload=payload or {},
    )
    tx.branches.append(branch)
    tx.updated_at = datetime.now(timezone.utc)
    return branch


def audit_global_tx(global_tx_id: str) -> SagaAuditReport | None:
    """对全局事务的分支流转执行一致性稽核与悬挂隐患探测。"""
    tx = _GLOBAL_TX_STORE.get(global_tx_id)
    if not tx:
        return None

    # 按服务名和动作对分支归组
    service_action_branches: dict[tuple[str, str], list[BranchTxRecord]] = {}
    for b in tx.branches:
        k = (b.service_name, b.action_name)
        if k not in service_action_branches:
            service_action_branches[k] = []
        service_action_branches[k].append(b)

    detected_anomaly = SagaAnomalyType.NONE
    anomaly_desc = ""
    remediation: list[str] = []

    pending_branches = [b for b in tx.branches if b.status == BranchStatus.PENDING]
    # 1. 检查是否存在“悬挂事务”与“空补偿”
    # 在 TCC 中：如果出现 CANCEL 早于 TRY 到达（或先于 TRY 记录），属于空补偿；若后续又收到 TRY，则产生悬挂！
    for (service, action), b_list in service_action_branches.items():
        stages = [b.stage for b in b_list]

        # 检查空补偿 (有 CANCEL/COMPENSATE 但无 TRY/FORWARD)
        has_cancel = BranchStage.CANCEL in stages or BranchStage.COMPENSATE in stages
        has_try = BranchStage.TRY in stages or BranchStage.FORWARD in stages

        if has_cancel and not has_try:
            detected_anomaly = SagaAnomalyType.EMPTY_COMPENSATION
            anomaly_desc = f"微服务 [{service}] 的动作 [{action}] 检测到空补偿异常：未曾执行过 Try/Forward 即收到了 Cancel/Compensate 请求。"
            remediation = [
                "在 Cancel/Compensate 接口逻辑中必须先检查是否存在对应的 Try 事务记录",
                "若无 Try 记录应直接返回成功并在本地写入防悬挂防空补偿事务标记",
            ]
            tx.status = GlobalTxStatus.HANGING
            break

        # 检查悬挂事务 (CANCEL 出现的位置在 TRY 之前，或 CANCEL 成功但 TRY 长期 PENDING/晚到)
        if has_cancel and has_try:
            cancel_idx = min(i for i, st in enumerate(stages) if st in (BranchStage.CANCEL, BranchStage.COMPENSATE))
            try_idx = min(i for i, st in enumerate(stages) if st in (BranchStage.TRY, BranchStage.FORWARD))
            if cancel_idx < try_idx:
                detected_anomaly = SagaAnomalyType.HANGING_TRANSACTION
                anomaly_desc = f"微服务 [{service}] 的动作 [{action}] 遭遇严重悬挂事务：Cancel 补偿请求先于 Try 到达执行，随后晚到的 Try 产生了资源冻结但永无后续 Confirm/Cancel。"
                remediation = [
                    "在 Try 接口执行前先检查是否已存在当前全局事务的 Cancel 记录，若已 Cancel 则拒绝 Try 执行并回滚",
                    "通过分布式锁或唯一事务凭据表保证 Try 与 Cancel 的严格串行防悬挂状态机",
                ]
                tx.status = GlobalTxStatus.HANGING
                break

    # 2. 检查超时未决 (若无上述异常)
    if detected_anomaly == SagaAnomalyType.NONE:
        now = datetime.now(timezone.utc)
        elapsed_sec = (now - tx.started_at).total_seconds()

        pending_branches = [b for b in tx.branches if b.status == BranchStatus.PENDING]
        if pending_branches and elapsed_sec > tx.timeout_seconds:
            detected_anomaly = SagaAnomalyType.TIMEOUT_PENDING
            p_svcs = [b.service_name for b in pending_branches]
            anomaly_desc = f"全局事务已超时 ({round(elapsed_sec, 1)}s > {tx.timeout_seconds}s)，以下服务分支长期处于 PENDING 悬挂未决状态: {', '.join(p_svcs)}。"
            remediation = [
                "触发事务协调器 (TC) 对超时分支主动轮询或发送 Cancel 回滚指令",
                "检查下游网络连通性或排查死锁状态",
            ]
            tx.status = GlobalTxStatus.TIMEOUT

    # 3. 检查部分提交与补偿失衡
    if detected_anomaly == SagaAnomalyType.NONE:
        # 统计成功分支
        confirmed_count = sum(
            1
            for b in tx.branches
            if b.stage in (BranchStage.CONFIRM, BranchStage.FORWARD) and b.status == BranchStatus.SUCCESS
        )
        failed_count = sum(1 for b in tx.branches if b.status == BranchStatus.FAILED)
        canceled_count = sum(
            1
            for b in tx.branches
            if b.stage in (BranchStage.CANCEL, BranchStage.COMPENSATE) and b.status == BranchStatus.SUCCESS
        )

        if failed_count > 0 and canceled_count == 0 and confirmed_count > 0:
            detected_anomaly = SagaAnomalyType.PARTIAL_COMMIT_FAILURE
            anomaly_desc = f"检测到跨服务数据最终一致性撕裂：存在 {confirmed_count} 个分支已确认提交，但存在 {failed_count} 个失败分支且未触发补偿回滚！"
            remediation = [
                "立即调用补偿协调器向所有已确认分支重试发送 Cancel/Compensate 指令",
                "人工介入对账并核实相关微服务数据库数据完整性",
            ]
            tx.status = GlobalTxStatus.INCONSISTENT
        elif failed_count > 0 and canceled_count > 0:
            tx.status = GlobalTxStatus.ROLLED_BACK
            anomaly_desc = "部分分支失败，已成功触发全量逆向补偿回滚，全局事务安全退出。"
        elif confirmed_count > 0 and failed_count == 0 and not pending_branches:
            tx.status = GlobalTxStatus.COMMITTED
            anomaly_desc = "所有微服务分支事务均成功执行并确认，全局数据最终一致性达标。"

    is_consistent = detected_anomaly == SagaAnomalyType.NONE and tx.status in (
        GlobalTxStatus.COMMITTED,
        GlobalTxStatus.ROLLED_BACK,
    )

    return SagaAuditReport(
        global_tx_id=tx.global_tx_id,
        business_key=tx.business_key,
        pattern=tx.pattern,
        status=tx.status,
        is_consistent=is_consistent,
        detected_anomaly=detected_anomaly,
        anomaly_description=anomaly_desc,
        branches=list(tx.branches),
        remediation_advice=remediation,
    )


def list_active_and_hanging_transactions() -> list[dict[str, Any]]:
    """查询全网处于未决、悬挂或异常状态的全局事务。"""
    results = []
    for tx in _GLOBAL_TX_STORE.values():
        audit = audit_global_tx(tx.global_tx_id)
        if not audit:
            continue
        results.append(
            {
                **tx.to_dict(),
                "is_consistent": audit.is_consistent,
                "detected_anomaly": audit.detected_anomaly.value,
                "anomaly_description": audit.anomaly_description,
            }
        )
    return results


def simulate_saga_scenario(scenario_key: str) -> SagaAuditReport:
    """仿真预设的分布式事务场景并返回审计报告。"""
    key = scenario_key.lower().strip()
    gid = f"gtx_sim_{key}_{uuid.uuid4().hex[:6]}"

    if key == "hanging":
        # 典型悬挂事务场景：Cancel 先于 Try 到达被执行，之后晚到的 Try 悬挂
        tx = record_global_tx(global_tx_id=gid, business_key=f"order_{uuid.uuid4().hex[:6]}", pattern="TCC")
        record_branch_tx(gid, "order-service", "create_order", stage="TRY", status="SUCCESS", duration_ms=45.0)
        # pay-service 先收到 CANCEL
        record_branch_tx(gid, "pay-service", "deduct_balance", stage="CANCEL", status="SUCCESS", duration_ms=20.0)
        # pay-service 随后才收到晚到的 TRY -> 悬挂！
        record_branch_tx(gid, "pay-service", "deduct_balance", stage="TRY", status="SUCCESS", duration_ms=60.0)
    elif key == "empty_compensation":
        # 空补偿场景：从未调用过扣款 Try，却收到了 Cancel
        tx = record_global_tx(global_tx_id=gid, business_key=f"order_{uuid.uuid4().hex[:6]}", pattern="TCC")
        record_branch_tx(gid, "order-service", "create_order", stage="TRY", status="SUCCESS", duration_ms=30.0)
        record_branch_tx(gid, "inventory-service", "lock_stock", stage="CANCEL", status="SUCCESS", duration_ms=15.0)
    elif key == "timeout":
        # 超时未决场景
        tx = record_global_tx(
            global_tx_id=gid, business_key=f"order_{uuid.uuid4().hex[:6]}", pattern="TCC", timeout_seconds=0.01
        )
        record_branch_tx(gid, "order-service", "create_order", stage="TRY", status="SUCCESS", duration_ms=20.0)
        record_branch_tx(gid, "pay-service", "deduct_balance", stage="TRY", status="PENDING", duration_ms=0.0)
        # 强制设置更早的开始时间触发超时
        tx.started_at = datetime.fromtimestamp(1000000000.0, timezone.utc)
    else:
        # 正常全部分支确认提交场景
        tx = record_global_tx(global_tx_id=gid, business_key=f"order_{uuid.uuid4().hex[:6]}", pattern="TCC")
        record_branch_tx(gid, "order-service", "create_order", stage="TRY", status="SUCCESS", duration_ms=30.0)
        record_branch_tx(gid, "order-service", "create_order", stage="CONFIRM", status="SUCCESS", duration_ms=15.0)
        record_branch_tx(gid, "pay-service", "deduct_balance", stage="TRY", status="SUCCESS", duration_ms=45.0)
        record_branch_tx(gid, "pay-service", "deduct_balance", stage="CONFIRM", status="SUCCESS", duration_ms=25.0)

    audit = audit_global_tx(gid)
    assert audit is not None
    return audit


def clear_saga_store() -> int:
    """清空全局事务存储仓库。"""
    c = len(_GLOBAL_TX_STORE)
    _GLOBAL_TX_STORE.clear()
    return c
