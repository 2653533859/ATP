"""失败堆栈与异常语义指纹提取器服务 (T1.1)

对自动化测试执行失败的报错信息与堆栈轨迹执行归一化清洗与特征提取，生成稳定唯一的 64 位异常指纹:
1. 动态易变要素归一化清洗 (内存地址 0x*、UUID、时间戳、IP端口等参数脱敏抹平);
2. 业务代码帧智能过滤 (排除 pytest/unittest/asyncio 框架内部杂质帧，提炼核心业务调用帧);
3. 核心语义特征抽取 (异常类型、归一化报错消息、最深业务帧路径、端点上下文);
4. 64 字符十六进制 SHA-256 故障语义指纹生成 (FailureFingerprintResult)。
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class NormalizedStackFrame:
    file_path: str
    function_name: str
    code_line: str
    is_business_code: bool
    line_number: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FailureFingerprintResult:
    fingerprint_id: str
    failure_fingerprint: str  # 64 位十六进制 SHA-256 唯一指纹
    exception_type: str
    normalized_message: str
    root_cause_frame: Optional[NormalizedStackFrame]
    business_frames_count: int
    raw_frames_count: int
    sanitized_stack_trace: str
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fingerprint_id": self.fingerprint_id,
            "failure_fingerprint": self.failure_fingerprint,
            "exception_type": self.exception_type,
            "normalized_message": self.normalized_message,
            "root_cause_frame": self.root_cause_frame.to_dict() if self.root_cause_frame else None,
            "business_frames_count": self.business_frames_count,
            "raw_frames_count": self.raw_frames_count,
            "sanitized_stack_trace": self.sanitized_stack_trace,
            "generated_at": self.generated_at,
        }


# 框架非业务杂质路径特征
FRAMEWORK_PATH_PATTERNS = [
    r".*site-packages.*",
    r".*dist-packages.*",
    r".*pytest.*",
    r".*_pytest.*",
    r".*pluggy.*",
    r".*asyncio/.*",
    r".*unittest/.*",
    r".*starlette/.*",
    r".*fastapi/.*",
    r".*node_modules.*",
]


def sanitize_dynamic_tokens(text: str) -> str:
    """消除易变的动态随机变量（内存地址、UUID、时间戳、IP端口）"""
    if not text:
        return ""
    s = text

    # 1. 替换内存十六进制地址: 0x7f9a8b1c -> <HEX_ADDR>
    s = re.sub(r"0x[0-9a-fA-F]{4,16}\b", "<HEX_ADDR>", s)

    # 2. 替换标准 UUID / GUID
    s = re.sub(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        "<UUID>",
        s,
    )

    # 3. 替换 ISO 时间戳或日期时间
    s = re.sub(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?", "<TIMESTAMP>", s)

    # 4. 替换 IP 与端口
    s = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}\b", "<HOST:PORT>", s)
    s = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<IP_ADDR>", s)

    # 5. 替换常见的动态 ID，例如 user_123456 -> user_<ID>
    s = re.sub(r"\b(user|order|pay|task|case|run|cert|exp)_[0-9a-fA-F]{6,16}\b", r"\1_<ID>", s)

    return s.strip()


def _is_business_path(path: str) -> bool:
    """判定是否为产品工程自身的业务代码路径"""
    norm = path.replace("\\", "/").lower()
    for pat in FRAMEWORK_PATH_PATTERNS:
        if re.search(pat, norm):
            return False
    return True


def parse_and_clean_stack_trace(raw_stack: str) -> tuple[List[NormalizedStackFrame], str]:
    """解析并清洗堆栈帧，识别业务代码帧"""
    lines = raw_stack.splitlines()
    frames: List[NormalizedStackFrame] = []
    sanitized_lines: List[str] = []

    # 匹配常见的 Python 堆栈行: File "/path/to/file.py", line 42, in my_func
    py_frame_pattern = re.compile(r'^\s*File\s+"([^"]+)",\s*line\s+(\d+),\s*in\s+(.+)$')

    for i, line in enumerate(lines):
        clean_line = sanitize_dynamic_tokens(line)
        sanitized_lines.append(clean_line)

        m = py_frame_pattern.match(line)
        if m:
            file_p = m.group(1).strip()
            line_no = int(m.group(2))
            func_name = m.group(3).strip()
            # 获取下一行代码内容
            code_text = ""
            if i + 1 < len(lines):
                code_text = lines[i + 1].strip()

            is_biz = _is_business_path(file_p)
            frames.append(
                NormalizedStackFrame(
                    file_path=file_p,
                    line_number=line_no,
                    function_name=func_name,
                    code_line=sanitize_dynamic_tokens(code_text),
                    is_business_code=is_biz,
                )
            )

    return frames, "\n".join(sanitized_lines)


def extract_failure_fingerprint(
    raw_error_message: str,
    raw_stack_trace: str,
    exception_type: Optional[str] = None,
    target_endpoint: Optional[str] = None,
) -> FailureFingerprintResult:
    """提取归一化异常语义特征并生成确定性 64 位 SHA-256 失败指纹"""
    fingerprint_id = f"fp_{uuid.uuid4().hex[:10]}"

    # 1. 提取异常类型 (如果未提供则从错误信息或堆栈最后一行提取)
    exc_type = exception_type
    if not exc_type:
        m = re.search(r"\b([A-Za-z_]+(?:Error|Exception|Timeout|Failure|Fault))\b", raw_error_message)
        if m:
            exc_type = m.group(1)
        else:
            # 尝试在堆栈最后几行寻找
            stack_lines = raw_stack_trace.strip().splitlines()
            for l in reversed(stack_lines[-3:]):
                m_end = re.match(r"^([A-Za-z_]+(?:Error|Exception|Timeout|Failure|Fault))(?::|\b)", l.strip())
                if m_end:
                    exc_type = m_end.group(1)
                    break
    exc_type = exc_type or "UnknownAssertionFailure"

    # 2. 清洗报错信息
    norm_msg = sanitize_dynamic_tokens(raw_error_message)

    # 3. 解析与清洗堆栈帧
    frames, sanitized_stack = parse_and_clean_stack_trace(raw_stack_trace)

    # 4. 提取核心业务帧 (Root Cause Frame: 最后一个业务帧最接近异常抛出源头)
    biz_frames = [f for f in frames if f.is_business_code]
    root_cause_frame: Optional[NormalizedStackFrame] = (
        biz_frames[-1] if biz_frames else (frames[-1] if frames else None)
    )

    # 5. 构建确定性语义特征摘要字典
    semantic_signature = {
        "exception_type": exc_type,
        "normalized_message": norm_msg,
        "root_file": root_cause_frame.file_path if root_cause_frame else "",
        "root_func": root_cause_frame.function_name if root_cause_frame else "",
        "root_code": root_cause_frame.code_line if root_cause_frame else "",
        "endpoint": target_endpoint or "",
    }

    # 6. 计算 64 位 SHA-256 指纹
    canonical_sig = json.dumps(semantic_signature, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    fingerprint_sha256 = hashlib.sha256(canonical_sig.encode("utf-8")).hexdigest()

    return FailureFingerprintResult(
        fingerprint_id=fingerprint_id,
        failure_fingerprint=fingerprint_sha256,
        exception_type=exc_type,
        normalized_message=norm_msg,
        root_cause_frame=root_cause_frame,
        business_frames_count=len(biz_frames),
        raw_frames_count=len(frames),
        sanitized_stack_trace=sanitized_stack,
    )
