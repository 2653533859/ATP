"""生产流量 OpenAPI/Protobuf 契约动态逆向提取推导器服务 (T3.1)。

负责从海量实时微服务网关生产流量中自动逆向推导出接口的完整契约规范：
1. 自适应多样本 Schema 递归归纳 (推导字段类型、必填性 required、枚举 enum、嵌套结构)；
2. 自动生成标准 OpenAPI 3.0 / JSON Schema 契约定义；
3. 自动生成 Protobuf 3 语法 IDL 消息定义；
4. 捕获真实生产隐藏参数与非预期字段，消除开发设计文档与现网代码间的契约漂移。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import re
from typing import Any
import uuid

logger = logging.getLogger(__name__)

# 格式自动识别正则
ISO8601_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$")
UUID_REGEX = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def _safe_json_parse(raw: Any) -> Any:
    """安全解析 JSON 字符串。"""
    if isinstance(raw, str):
        trimmed = raw.strip()
        if (trimmed.startswith("{") and trimmed.endswith("}")) or (trimmed.startswith("[") and trimmed.endswith("]")):
            try:
                return json.loads(trimmed)
            except Exception:
                pass
    return raw


def infer_type_and_format(val: Any) -> tuple[str, str | None]:
    """推断单值的类型与格式 (OpenAPI 规范)。"""
    if val is None:
        return "null", None
    if isinstance(val, bool):
        return "boolean", None
    if isinstance(val, int):
        return "integer", "int64" if abs(val) > 2147483647 else "int32"
    if isinstance(val, float):
        return "number", "double"
    if isinstance(val, list):
        return "array", None
    if isinstance(val, dict):
        return "object", None
    if isinstance(val, str):
        if ISO8601_REGEX.match(val):
            return "string", "date-time"
        if UUID_REGEX.match(val):
            return "string", "uuid"
        if EMAIL_REGEX.match(val):
            return "string", "email"
        return "string", None
    return "string", None


def infer_json_schema_from_samples(samples: list[Any]) -> dict[str, Any]:
    """从多个数据样本中自适应归纳推导出完整的 OpenAPI / JSON Schema。"""
    valid_samples = [_safe_json_parse(s) for s in samples if s is not None and s != ""]
    if not valid_samples:
        return {"type": "object", "properties": {}}

    # 1. 检查顶级类型
    first = valid_samples[0]
    if isinstance(first, list):
        # 数组类型：合并所有样本中的子项
        all_items: list[Any] = []
        for s in valid_samples:
            if isinstance(s, list):
                all_items.extend(s)
        item_schema = infer_json_schema_from_samples(all_items) if all_items else {"type": "string"}
        return {"type": "array", "items": item_schema}

    if not isinstance(first, dict):
        # 简单标量
        t, f = infer_type_and_format(first)
        res: dict[str, Any] = {"type": t}
        if f:
            res["format"] = f
        return res

    # 2. 对象类型：多样本键名聚合
    total_samples = len(valid_samples)
    key_counts: dict[str, int] = {}
    key_values: dict[str, list[Any]] = {}

    for s in valid_samples:
        if isinstance(s, dict):
            for k, v in s.items():
                key_counts[k] = key_counts.get(k, 0) + 1
                key_values.setdefault(k, []).append(v)

    properties: dict[str, Any] = {}
    required: list[str] = []

    for k in sorted(key_counts.keys()):
        # 若该字段在 100% 的有效样本中均出现，判定为 required 必填
        if key_counts[k] == total_samples:
            required.append(k)

        vals = key_values[k]
        # 分析字段的类型集合
        types_set = set()
        formats_set = set()
        for v in vals:
            vt, vf = infer_type_and_format(v)
            types_set.add(vt)
            if vf:
                formats_set.add(vf)

        # 类型归一处理 (如同时出现 integer 与 number，提升为 number)
        if types_set == {"integer", "number"} or types_set == {"number"}:
            final_type = "number"
        elif "null" in types_set and len(types_set) == 2:
            final_type = next(t for t in types_set if t != "null")
        elif len(types_set) == 1:
            final_type = next(iter(types_set))
        else:
            final_type = "string"  # 复合异构降级为 string

        field_schema: dict[str, Any] = {"type": final_type}
        if formats_set and len(formats_set) == 1 and final_type == "string":
            field_schema["format"] = next(iter(formats_set))

        # 嵌套子对象/数组递归提取
        if final_type == "object":
            sub_dicts = [v for v in vals if isinstance(v, dict)]
            field_schema = infer_json_schema_from_samples(sub_dicts)
        elif final_type == "array":
            sub_lists = [item for sub in vals if isinstance(sub, list) for item in sub]
            field_schema = {
                "type": "array",
                "items": infer_json_schema_from_samples(sub_lists) if sub_lists else {"type": "string"},
            }

        # 自动推导枚举 (当样本数 >= 3 且独立字符串取值范围在 2~5 之间)
        if final_type == "string" and total_samples >= 3:
            distinct_str_vals = sorted(list({str(v) for v in vals if v is not None}))
            if 2 <= len(distinct_str_vals) <= 5 and all(len(s) <= 32 for s in distinct_str_vals):
                field_schema["enum"] = distinct_str_vals

        properties[k] = field_schema

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = sorted(required)

    return schema


def generate_protobuf_from_schema(message_name: str, schema: dict[str, Any]) -> str:
    """将推导出的 JSON Schema 转换为标准的 Protobuf 3 语法结构体定义。"""
    clean_name = re.sub(r"[^a-zA-Z0-9_]", "", message_name).capitalize() or "Message"
    lines = [
        'syntax = "proto3";',
        "",
        f"message {clean_name} {{",
    ]

    props = schema.get("properties", {})
    field_idx = 1

    for k, field_schema in sorted(props.items()):
        f_type = field_schema.get("type", "string")
        f_format = field_schema.get("format")

        proto_type = "string"
        if f_type == "integer":
            proto_type = "int64" if f_format == "int64" else "int32"
        elif f_type == "number":
            proto_type = "double"
        elif f_type == "boolean":
            proto_type = "bool"
        elif f_type == "array":
            sub_item = field_schema.get("items", {})
            sub_t = sub_item.get("type", "string")
            if sub_t == "integer":
                proto_type = "repeated int32"
            elif sub_t == "number":
                proto_type = "repeated double"
            elif sub_t == "boolean":
                proto_type = "repeated bool"
            else:
                proto_type = "repeated string"
        elif f_type == "object":
            proto_type = "bytes"  # 复杂内嵌对象默认以 bytes 映射，保证向后兼容

        # 字段命名规范化
        clean_field_name = re.sub(r"[^a-zA-Z0-9_]", "_", k).lower()
        lines.append(f"  {proto_type} {clean_field_name} = {field_idx};")
        field_idx += 1

    lines.append("}")
    return "\n".join(lines)


@dataclass
class ExtractedContract:
    contract_id: str
    endpoint: str
    method: str
    path: str
    protocol: str
    samples_count: int
    request_schema: dict[str, Any]
    response_schemas: dict[str, Any]  # status_code_str -> schema
    query_parameters: list[dict[str, Any]]
    header_parameters: list[dict[str, Any]]
    protobuf_definition: str
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "endpoint": self.endpoint,
            "method": self.method,
            "path": self.path,
            "protocol": self.protocol,
            "samples_count": self.samples_count,
            "request_schema": self.request_schema,
            "response_schemas": self.response_schemas,
            "query_parameters": self.query_parameters,
            "header_parameters": self.header_parameters,
            "protobuf_definition": self.protobuf_definition,
            "extracted_at": self.extracted_at.isoformat(),
        }


@dataclass
class ExtractionBatchReport:
    report_id: str
    total_traffic_analyzed: int
    contracts_extracted_count: int
    contracts: list[ExtractedContract]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "total_traffic_analyzed": self.total_traffic_analyzed,
            "contracts_extracted_count": self.contracts_extracted_count,
            "contracts": [c.to_dict() for c in self.contracts],
            "created_at": self.created_at.isoformat(),
        }


# 全局内存契约仓库
_EXTRACTED_CONTRACTS: dict[str, ExtractedContract] = {}
_BATCH_EXTRACTION_REPORTS: dict[str, ExtractionBatchReport] = {}


def extract_contract_from_traffic(
    endpoint: str,
    traffic_samples: list[dict[str, Any]],
    protocol: str = "HTTP",
) -> ExtractedContract:
    """从同一端点的多个真实流量调用样本中逆向推导完整的接口契约规范。"""
    contract_id = f"ct_{uuid.uuid4().hex[:10]}"
    method = endpoint.split()[0].upper() if " " in endpoint else "POST"
    path = endpoint.split()[1] if " " in endpoint else endpoint

    # 1. 提取所有请求体样本
    req_samples = [s.get("request_body") for s in traffic_samples if s.get("request_body")]
    request_schema = infer_json_schema_from_samples(req_samples)

    # 2. 按状态码分组提取响应体样本
    resp_by_status: dict[str, list[Any]] = {}
    for s in traffic_samples:
        st = str(s.get("response_status_code", s.get("status_code", 200)))
        resp_by_status.setdefault(st, []).append(s.get("response_body"))

    response_schemas: dict[str, Any] = {}
    for st_code, resps in resp_by_status.items():
        response_schemas[st_code] = infer_json_schema_from_samples(resps)

    # 3. 提取 Query 参数规范
    query_samples = [s.get("query_params") for s in traffic_samples if isinstance(s.get("query_params"), dict)]
    query_schema = infer_json_schema_from_samples(query_samples)
    query_params: list[dict[str, Any]] = []
    for qk, qv in query_schema.get("properties", {}).items():
        query_params.append(
            {
                "name": qk,
                "type": qv.get("type", "string"),
                "required": qk in query_schema.get("required", []),
            }
        )

    # 4. 提取出站 Header 参数规范 (过滤动态头)
    header_samples = [s.get("headers") for s in traffic_samples if isinstance(s.get("headers"), dict)]
    header_params: list[dict[str, Any]] = []
    if header_samples:
        h_schema = infer_json_schema_from_samples(header_samples)
        for hk, hv in h_schema.get("properties", {}).items():
            if hk.lower() in ("content-type", "accept", "authorization", "x-client-version"):
                header_params.append(
                    {
                        "name": hk,
                        "type": hv.get("type", "string"),
                        "required": hk in h_schema.get("required", []),
                    }
                )

    # 5. 生成 Protobuf 3 IDL
    msg_name = path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
    proto_def = generate_protobuf_from_schema(f"{method}_{msg_name}_request", request_schema)

    contract = ExtractedContract(
        contract_id=contract_id,
        endpoint=endpoint.strip(),
        method=method,
        path=path,
        protocol=protocol.upper(),
        samples_count=len(traffic_samples),
        request_schema=request_schema,
        response_schemas=response_schemas,
        query_parameters=query_params,
        header_parameters=header_params,
        protobuf_definition=proto_def,
    )

    _EXTRACTED_CONTRACTS[contract_id] = contract
    logger.info("成功逆向推导接口契约 [%s]: %s (基于 %d 个样本)", contract_id, endpoint, len(traffic_samples))
    return contract


def batch_extract_contracts_from_traffic(
    traffic_records: list[dict[str, Any]],
) -> ExtractionBatchReport:
    """批量对海量流量进行按接口端点分组聚合，批量逆向推导全部接口契约。"""
    batch_id = f"ebp_{uuid.uuid4().hex[:12]}"

    # 按方法与路径端点分组
    endpoint_groups: dict[str, list[dict[str, Any]]] = {}
    for r in traffic_records:
        ep = str(r.get("endpoint", "") or r.get("path_or_endpoint", "/"))
        method = str(r.get("method", "GET")).upper()
        full_ep = f"{method} {ep}" if not ep.startswith(method) else ep
        endpoint_groups.setdefault(full_ep, []).append(r)

    contracts: list[ExtractedContract] = []
    for ep, samples in endpoint_groups.items():
        c = extract_contract_from_traffic(endpoint=ep, traffic_samples=samples)
        contracts.append(c)

    report = ExtractionBatchReport(
        report_id=batch_id,
        total_traffic_analyzed=len(traffic_records),
        contracts_extracted_count=len(contracts),
        contracts=contracts,
    )
    _BATCH_EXTRACTION_REPORTS[batch_id] = report
    return report


def get_extracted_contract(contract_id: str) -> ExtractedContract | None:
    """根据 ID 获取契约详情。"""
    return _EXTRACTED_CONTRACTS.get(contract_id)


def get_contract_by_endpoint(endpoint: str) -> ExtractedContract | None:
    """根据端点获取最新逆向推导的契约。"""
    ep_clean = endpoint.strip()
    candidates = [c for c in _EXTRACTED_CONTRACTS.values() if c.endpoint.lower() == ep_clean.lower()]
    if not candidates:
        return None
    candidates.sort(key=lambda c: c.extracted_at, reverse=True)
    return candidates[0]


def list_extracted_contracts() -> list[ExtractedContract]:
    """查询历史推导契约列表。"""
    contracts = list(_EXTRACTED_CONTRACTS.values())
    contracts.sort(key=lambda c: c.extracted_at, reverse=True)
    return contracts


def clear_extracted_contracts() -> int:
    """清空提取契约缓存。"""
    count = len(_EXTRACTED_CONTRACTS)
    _EXTRACTED_CONTRACTS.clear()
    _BATCH_EXTRACTION_REPORTS.clear()
    return count
