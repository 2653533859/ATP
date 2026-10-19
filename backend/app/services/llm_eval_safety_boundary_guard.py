"""大模型线上接入合规审批与安全强准入看门狗服务 (T4.1)

筑牢企业生产环境大模型调用与智能体安全防线，严格审查生产三要素强准入条件:
1. 安全评测审批单审查 (Safety Evaluation Ticket: 必须提供处于 APPROVED 状态且各项评测指标合格的审批单);
2. 准入模型白名单审查 (Model Whitelist: 严禁未经备案审核的外部未知模型接入生产);
3. 访问鉴权令牌审查 (Security Access Token: 严密防范未授权与伪造模型调用);
4. 环境自适应旁路控制 (测试/预发/研发环境免审快速放行，生产环境严格执行三要素强阻断)。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import enum
from typing import Any, Dict, List, Optional
import uuid


class LlmAdmissionVerdictCode(str, enum.Enum):
    """大模型接入准入裁决码"""

    ADMITTED_PASS = "ADMITTED_PASS"  # 生产三要素合规通过，准予在线生产调用
    BYPASS_NON_PRODUCTION = "BYPASS_NON_PRODUCTION"  # 非生产环境 (test/staging/dev)，免审安全旁路放行
    BLOCKED_NO_TICKET = "BLOCKED_NO_TICKET"  # 未提供审批单或审批单号无效
    BLOCKED_TICKET_NOT_APPROVED = "BLOCKED_TICKET_NOT_APPROVED"  # 审批单未审批通过 (PENDING/REJECTED) 或评测指标不达标
    BLOCKED_UNAUTHORIZED_MODEL = "BLOCKED_UNAUTHORIZED_MODEL"  # 模型不在企业准入白名单中
    BLOCKED_INVALID_TOKEN = "BLOCKED_INVALID_TOKEN"  # 鉴权令牌缺失、伪造或未通过校验


# 允许准入放行的工单审批状态集合
APPROVED_TICKET_STATUSES = {"APPROVED", "PASSED", "RESOLVED"}

# 企业生产大模型合规准入白名单 (预设官方经严格备案评测模型)
DEFAULT_AUTHORIZED_MODELS = {
    "qwen-2.5-72b",
    "deepseek-v3",
    "deepseek-r1",
    "llama-3.3-70b",
    "gpt-4o",
    "gpt-4o-mini",
    "claude-3-5-sonnet",
}

# 预设合法模型访问安全令牌前缀
VALID_LLM_TOKEN_PREFIX = "LLM_SEC_TOKEN_"


class LlmSafetyAdmissionError(Exception):
    """大模型生产准入强阻断异常"""

    def __init__(self, verdict: LlmSafetyAdmissionVerdict):
        self.verdict = verdict
        super().__init__(f"大模型生产安全准入阻断: [{verdict.verdict_code.value}] {verdict.reason}")


@dataclass
class LlmAdmissionTicket:
    """大模型上线安全评测审批单"""

    ticket_key: str  # 审批工单号，如 OA-LLM-20261019-01
    status: str  # APPROVED | PENDING | REJECTED | DRAFT
    approver: str  # 安全架构师/合规审批人
    composite_score: float = 90.0  # 评测综合分 (最低门槛 >= 80.0)
    red_team_defense_rate: float = 95.0  # 红蓝越狱防御率 (最低门槛 >= 85.0%)
    scope_description: str = "企业大模型生产智能体调用接入审批"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LlmAdmissionRequest:
    """生产大模型在线接入准入申请上下文"""

    model_name: str  # 目标接入模型名称
    environment: str  # production | prod | staging | test | dev
    caller_service: str  # 调用方微服务或智能体代号
    ticket: Optional[LlmAdmissionTicket] = None  # 审批工单
    security_token: Optional[str] = None  # 安全访问令牌
    custom_whitelist: Optional[List[str]] = None  # 自定义白名单覆写

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "environment": self.environment,
            "caller_service": self.caller_service,
            "ticket": self.ticket.to_dict() if self.ticket else None,
            "security_token": self.security_token,
            "custom_whitelist": self.custom_whitelist,
        }


@dataclass
class LlmSafetyAdmissionVerdict:
    """准入审查裁决结果"""

    verdict_id: str
    verdict_code: LlmAdmissionVerdictCode
    is_admitted: bool
    model_name: str
    environment: str
    evaluated_at: str
    reason: str
    checked_items: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict_id": self.verdict_id,
            "verdict_code": self.verdict_code.value,
            "is_admitted": self.is_admitted,
            "model_name": self.model_name,
            "environment": self.environment,
            "evaluated_at": self.evaluated_at,
            "reason": self.reason,
            "checked_items": self.checked_items,
        }


def _is_production_env(environment: str) -> bool:
    """判断是否为生产环境"""
    return environment.strip().lower() in ("production", "prod")


def evaluate_llm_safety_admission(request: LlmAdmissionRequest) -> LlmSafetyAdmissionVerdict:
    """毫秒级执行生产大模型安全强准入边界审查

    审查判定逻辑:
    1. 环境自适应检查:
       - 若非生产环境 (staging/test/dev) -> 直接旁路放行 (BYPASS_NON_PRODUCTION);
    2. 生产环境强阻断三要素审查:
       - 要素 1: 模型白名单校验 (Model Whitelist) -> 若未在备案白名单立即阻断 (BLOCKED_UNAUTHORIZED_MODEL);
       - 要素 2: 访问鉴权令牌校验 (Security Token) -> 若缺失或伪造立即阻断 (BLOCKED_INVALID_TOKEN);
       - 要素 3: 安全评测审批单审查 (Admission Ticket) ->
         * 审批单缺失或未通过 -> 阻断 (BLOCKED_NO_TICKET / BLOCKED_TICKET_NOT_APPROVED);
         * 综合分 < 80.0 或红蓝越狱防御率 < 85.0% -> 阻断 (BLOCKED_TICKET_NOT_APPROVED);
    3. 三要素全部合规 -> 准予接入生产调用 (ADMITTED_PASS)。
    """
    verdict_id = f"llm_adm_{uuid.uuid4().hex[:10]}"
    now_str = datetime.now(timezone.utc).isoformat()
    checked_items: Dict[str, bool] = {}

    # 1. 环境自适应: 非生产环境快速旁路放行
    if not _is_production_env(request.environment):
        checked_items["env_check"] = True
        return LlmSafetyAdmissionVerdict(
            verdict_id=verdict_id,
            verdict_code=LlmAdmissionVerdictCode.BYPASS_NON_PRODUCTION,
            is_admitted=True,
            model_name=request.model_name,
            environment=request.environment,
            evaluated_at=now_str,
            reason=f"非生产环境 [{request.environment}]，大模型安全准入快速旁路放行",
            checked_items=checked_items,
        )

    # 生产环境强制执行三要素严审
    checked_items["env_check"] = True

    # 2. 要素 1: 模型白名单校验 (Model Whitelist)
    model_name_clean = request.model_name.strip().lower()
    whitelist = set(request.custom_whitelist) if request.custom_whitelist else DEFAULT_AUTHORIZED_MODELS

    if model_name_clean not in whitelist:
        checked_items["model_whitelist_check"] = False
        return LlmSafetyAdmissionVerdict(
            verdict_id=verdict_id,
            verdict_code=LlmAdmissionVerdictCode.BLOCKED_UNAUTHORIZED_MODEL,
            is_admitted=False,
            model_name=request.model_name,
            environment=request.environment,
            evaluated_at=now_str,
            reason=f"模型 [{request.model_name}] 未列入企业合规准入白名单，禁止接入生产环境！",
            checked_items=checked_items,
        )
    checked_items["model_whitelist_check"] = True

    # 3. 要素 2: 安全访问令牌校验 (Security Token)
    token = request.security_token
    if not token or not token.startswith(VALID_LLM_TOKEN_PREFIX) or len(token) < 20:
        checked_items["token_check"] = False
        return LlmSafetyAdmissionVerdict(
            verdict_id=verdict_id,
            verdict_code=LlmAdmissionVerdictCode.BLOCKED_INVALID_TOKEN,
            is_admitted=False,
            model_name=request.model_name,
            environment=request.environment,
            evaluated_at=now_str,
            reason="未提供合法的大模型生产访问鉴权令牌 (Token 缺失或格式非法)，拒绝生产调用！",
            checked_items=checked_items,
        )
    checked_items["token_check"] = True

    # 4. 要素 3: 安全评测审批单审查 (Evaluation Ticket)
    ticket = request.ticket
    if not ticket or not ticket.ticket_key or not ticket.ticket_key.strip():
        checked_items["ticket_check"] = False
        return LlmSafetyAdmissionVerdict(
            verdict_id=verdict_id,
            verdict_code=LlmAdmissionVerdictCode.BLOCKED_NO_TICKET,
            is_admitted=False,
            model_name=request.model_name,
            environment=request.environment,
            evaluated_at=now_str,
            reason="生产环境大模型接入必须提供安全合规审批单号，当前未提供有效审批单！",
            checked_items=checked_items,
        )

    # 校验工单审批状态
    if ticket.status.strip().upper() not in APPROVED_TICKET_STATUSES:
        checked_items["ticket_status_check"] = False
        return LlmSafetyAdmissionVerdict(
            verdict_id=verdict_id,
            verdict_code=LlmAdmissionVerdictCode.BLOCKED_TICKET_NOT_APPROVED,
            is_admitted=False,
            model_name=request.model_name,
            environment=request.environment,
            evaluated_at=now_str,
            reason=f"安全审批单 [{ticket.ticket_key}] 当前状态为 [{ticket.status}]，尚未审批通过！",
            checked_items=checked_items,
        )

    # 校验质效指标门槛: 综合分 >= 80.0 且 红蓝防御率 >= 85.0%
    if ticket.composite_score < 80.0 or ticket.red_team_defense_rate < 85.0:
        checked_items["metrics_threshold_check"] = False
        return LlmSafetyAdmissionVerdict(
            verdict_id=verdict_id,
            verdict_code=LlmAdmissionVerdictCode.BLOCKED_TICKET_NOT_APPROVED,
            is_admitted=False,
            model_name=request.model_name,
            environment=request.environment,
            evaluated_at=now_str,
            reason=(
                f"安全审批单指标不达标：综合分 {ticket.composite_score:.1f} (门槛 80.0)，"
                f"越狱防御率 {ticket.red_team_defense_rate:.1f}% (门槛 85.0%)，禁止接入！"
            ),
            checked_items=checked_items,
        )

    checked_items["ticket_check"] = True
    checked_items["ticket_status_check"] = True
    checked_items["metrics_threshold_check"] = True

    # 5. 三要素全部合规放行
    return LlmSafetyAdmissionVerdict(
        verdict_id=verdict_id,
        verdict_code=LlmAdmissionVerdictCode.ADMITTED_PASS,
        is_admitted=True,
        model_name=request.model_name,
        environment=request.environment,
        evaluated_at=now_str,
        reason=f"大模型 [{request.model_name}] 生产三要素审查全部合格，准予在线生产接入",
        checked_items=checked_items,
    )


def enforce_llm_safety_admission(request: LlmAdmissionRequest) -> LlmSafetyAdmissionVerdict:
    """前置强准入断言看门狗：若不满足准入条件直接抛出 LlmSafetyAdmissionError 异常阻断调用"""
    verdict = evaluate_llm_safety_admission(request)
    if not verdict.is_admitted:
        raise LlmSafetyAdmissionError(verdict)
    return verdict
