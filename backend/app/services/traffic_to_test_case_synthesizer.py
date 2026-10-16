"""真实流量请求聚类归一与自动化测试用例智能生成器 (T1.3)。

负责将网关旁路捕获的海量镜像流量进行特征指纹提取、聚类归一去重，
提取参数化数据集，并智能合成标准的 ATP 接口自动化测试用例 (TestCase) 与断言规范。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import re
from typing import Any
import uuid

from app.services.traffic_data_masker import mask_captured_traffic_item

logger = logging.getLogger(__name__)

# 动态 URL 参数归一化正则 (数字 ID、UUID、MD5)
PATH_NUM_ID_REGEX = re.compile(r"/\d+(?=/|$)")
PATH_UUID_REGEX = re.compile(r"/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}(?=/|$)")
PATH_HEX_REGEX = re.compile(r"/[0-9a-fA-F]{24,32}(?=/|$)")


def normalize_url_path(path: str) -> str:
    """将 URL 路径中的动态参数部分 (数字 ID / UUID) 归一化为占位符。"""
    res = PATH_UUID_REGEX.sub("/{uuid}", path)
    res = PATH_HEX_REGEX.sub("/{hex_id}", res)
    res = PATH_NUM_ID_REGEX.sub("/{id}", res)
    return res


def extract_schema_signature(data: Any) -> str:
    """提取 JSON 负载的 Schema 类型签名，用于识别请求体模式结构。"""
    if isinstance(data, dict):
        keys = sorted(data.keys())
        sub_sig = []
        for k in keys:
            val_type = type(data[k]).__name__
            sub_sig.append(f"{k}:{val_type}")
        return "{" + ",".join(sub_sig) + "}"
    if isinstance(data, list):
        if not data:
            return "[]"
        return f"[{type(data[0]).__name__}]"
    return type(data).__name__


@dataclass
class TrafficCluster:
    cluster_id: str
    fingerprint: str
    protocol: str
    method: str
    normalized_path: str
    status_code: int
    sample_count: int
    representative_traffic_id: str
    extracted_dataset_rows: list[dict[str, Any]] = field(default_factory=list)
    source_traffic_ids: list[str] = field(default_factory=list)
    schema_signature: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "fingerprint": self.fingerprint,
            "protocol": self.protocol,
            "method": self.method,
            "normalized_path": self.normalized_path,
            "status_code": self.status_code,
            "sample_count": self.sample_count,
            "representative_traffic_id": self.representative_traffic_id,
            "extracted_dataset_rows": self.extracted_dataset_rows,
            "source_traffic_ids": self.source_traffic_ids,
            "schema_signature": self.schema_signature,
        }


@dataclass
class SynthesizedCaseItem:
    case_id: str
    cluster_id: str
    name: str
    description: str
    protocol: str
    method: str
    url_path: str
    headers: dict[str, str]
    query_params_template: dict[str, str]
    request_body_template: str
    assertions: list[dict[str, Any]]
    dataset_rows: list[dict[str, Any]]
    source_traffic_ids: list[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "cluster_id": self.cluster_id,
            "name": self.name,
            "description": self.description,
            "protocol": self.protocol,
            "method": self.method,
            "url_path": self.url_path,
            "headers": self.headers,
            "query_params_template": self.query_params_template,
            "request_body_template": self.request_body_template,
            "assertions": self.assertions,
            "dataset_rows": self.dataset_rows,
            "source_traffic_ids": self.source_traffic_ids,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class SynthesisReport:
    report_id: str
    total_traffic_evaluated: int
    clusters_formed: int
    deduplication_ratio_pct: float
    synthesized_cases_count: int
    cases: list[SynthesizedCaseItem]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "total_traffic_evaluated": self.total_traffic_evaluated,
            "clusters_formed": self.clusters_formed,
            "deduplication_ratio_pct": round(self.deduplication_ratio_pct, 2),
            "synthesized_cases_count": self.synthesized_cases_count,
            "cases": [c.to_dict() for c in self.cases],
            "created_at": self.created_at.isoformat(),
        }


# 内存报告仓库
_SYNTHESIS_REPORTS: dict[str, SynthesisReport] = {}


def generate_synthesized_assertions(traffic: dict[str, Any]) -> list[dict[str, Any]]:
    """根据捕获的代表性流量特征自动生成智能校验断言。"""
    status_code = int(traffic.get("response_status_code", 200))
    duration_ms = float(traffic.get("duration_ms", 50.0))
    resp_body = traffic.get("response_body", "")

    assertions: list[dict[str, Any]] = [
        # 1. HTTP / gRPC 状态码断言
        {
            "target": "status_code",
            "operator": "eq",
            "expected": status_code,
            "description": f"验证响应状态码为 {status_code}",
        },
        # 2. 响应时延 SLA 断言 (允许 2 倍裕量，最低 200ms)
        {
            "target": "duration_ms",
            "operator": "le",
            "expected": max(200.0, round(duration_ms * 2.0, 1)),
            "description": f"验证接口响应耗时在 SLA 容忍区间 (<= {max(200.0, round(duration_ms * 2.0, 1))}ms)",
        },
    ]

    # 3. 业务体顶层关键字段断言
    if resp_body:
        try:
            parsed = json.loads(resp_body) if isinstance(resp_body, str) else resp_body
            if isinstance(parsed, dict):
                # 检查常见业务响应码 code / status / success
                for bk in ["code", "status", "success", "errcode"]:
                    if bk in parsed:
                        assertions.append(
                            {
                                "target": f"body.{bk}",
                                "operator": "eq",
                                "expected": parsed[bk],
                                "description": f"验证业务响应字段 {bk} 值为 {parsed[bk]}",
                            }
                        )
                        break
        except Exception:
            pass

    return assertions


def cluster_traffic_records(records: list[dict[str, Any]]) -> list[TrafficCluster]:
    """对原始或脱敏后的流量记录流进行特征提取与聚类归一。"""
    cluster_map: dict[str, TrafficCluster] = {}

    for item in records:
        protocol = str(item.get("protocol", "HTTP")).upper()
        method = str(item.get("method", "GET")).upper()
        raw_path = str(item.get("path_or_endpoint", "/"))
        normalized_path = normalize_url_path(raw_path)
        status_code = int(item.get("response_status_code", 200))

        # 提取 Request Body 的 Schema 签名
        req_body = item.get("request_body", "")
        body_sig = ""
        if req_body:
            try:
                parsed_body = json.loads(req_body) if isinstance(req_body, str) else req_body
                body_sig = extract_schema_signature(parsed_body)
            except Exception:
                body_sig = "text"

        # 构造聚类指纹: PROTOCOL + METHOD + NORMALIZED_PATH + STATUS + BODY_SIG
        fingerprint = f"{protocol}::{method}::{normalized_path}::{status_code}::{body_sig}"
        traffic_id = str(item.get("traffic_id", f"trf_{uuid.uuid4().hex}"))

        # 构建数据集行 (用于后续参数化执行)
        dataset_row = {
            "traffic_id": traffic_id,
            "raw_path": raw_path,
            "query_params": item.get("query_params", {}),
            "request_body": req_body,
            "expected_status": status_code,
        }

        if fingerprint not in cluster_map:
            cluster_id = f"cls_{uuid.uuid4().hex[:10]}"
            cluster_map[fingerprint] = TrafficCluster(
                cluster_id=cluster_id,
                fingerprint=fingerprint,
                protocol=protocol,
                method=method,
                normalized_path=normalized_path,
                status_code=status_code,
                sample_count=1,
                representative_traffic_id=traffic_id,
                extracted_dataset_rows=[dataset_row],
                source_traffic_ids=[traffic_id],
                schema_signature=body_sig,
            )
        else:
            cls = cluster_map[fingerprint]
            cls.sample_count += 1
            cls.source_traffic_ids.append(traffic_id)
            if len(cls.extracted_dataset_rows) < 20:  # 单簇保留至多 20 个参数化样本
                cls.extracted_dataset_rows.append(dataset_row)

    return list(cluster_map.values())


def synthesize_test_cases_from_traffic(
    records: list[dict[str, Any]],
    auto_mask_first: bool = True,
    max_dataset_rows_per_case: int = 10,
    case_name_prefix: str = "AUTO",
) -> SynthesisReport:
    """端到端智能合成测试用例与参数化测试数据集。"""
    if not records:
        report_id = f"syn_{uuid.uuid4().hex[:12]}"
        rep = SynthesisReport(
            report_id=report_id,
            total_traffic_evaluated=0,
            clusters_formed=0,
            deduplication_ratio_pct=0.0,
            synthesized_cases_count=0,
            cases=[],
        )
        _SYNTHESIS_REPORTS[report_id] = rep
        return rep

    # 1. 安全合规：若开启 auto_mask_first，先对所有原始流量执行深度脱敏
    cleaned_records = records
    if auto_mask_first:
        cleaned_records = [mask_captured_traffic_item(r) for r in records]

    # 2. 流量特征指纹聚类
    clusters = cluster_traffic_records(cleaned_records)

    # 3. 统计去重率
    total_eval = len(records)
    cluster_count = len(clusters)
    dedup_ratio = 0.0
    if total_eval > 0:
        dedup_ratio = max(0.0, (1.0 - (cluster_count / total_eval)) * 100.0)

    # 4. 根据每个簇合成 ATP 标准 TestCase
    synthesized_cases: list[SynthesizedCaseItem] = []

    # 建立 traffic_id -> record 索引，便于提取代表性详情
    record_index = {str(r.get("traffic_id")): r for r in cleaned_records}

    for cluster in clusters:
        rep_record = record_index.get(cluster.representative_traffic_id, {})
        case_id = f"tc_syn_{uuid.uuid4().hex[:10]}"

        # 用例命名：前缀 + 方法 + 归一化路径 + 状态码
        clean_path_for_name = cluster.normalized_path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
        case_name = f"{case_name_prefix}_{cluster.method}_{clean_path_for_name}_{cluster.status_code}"

        desc = (
            f"由 ATP 生产流量智能合成引擎生成。来源于 {cluster.sample_count} 条真实镜像流量聚类，"
            f"覆盖接口 {cluster.method} {cluster.normalized_path}，预期状态码 {cluster.status_code}。"
        )

        # 智能断言
        assertions = generate_synthesized_assertions(rep_record)

        # 模板化请求体
        req_body = str(rep_record.get("request_body", ""))

        # 限制每条用例绑定的数据集行数
        dataset_rows = cluster.extracted_dataset_rows[:max_dataset_rows_per_case]

        # 提取代表性请求头 (过滤掉已失效的临时追踪头)
        raw_headers = rep_record.get("headers", {})
        safe_headers: dict[str, str] = {}
        for hk, hv in raw_headers.items():
            if hk.lower() in ("content-type", "accept", "user-agent", "authorization"):
                safe_headers[hk] = hv

        case_item = SynthesizedCaseItem(
            case_id=case_id,
            cluster_id=cluster.cluster_id,
            name=case_name,
            description=desc,
            protocol=cluster.protocol,
            method=cluster.method,
            url_path=cluster.normalized_path,
            headers=safe_headers,
            query_params_template=rep_record.get("query_params", {}),
            request_body_template=req_body,
            assertions=assertions,
            dataset_rows=dataset_rows,
            source_traffic_ids=cluster.source_traffic_ids,
        )
        synthesized_cases.append(case_item)

    report_id = f"syn_{uuid.uuid4().hex[:12]}"
    report = SynthesisReport(
        report_id=report_id,
        total_traffic_evaluated=total_eval,
        clusters_formed=cluster_count,
        deduplication_ratio_pct=dedup_ratio,
        synthesized_cases_count=len(synthesized_cases),
        cases=synthesized_cases,
    )

    _SYNTHESIS_REPORTS[report_id] = report
    logger.info(
        "成功从 %d 条镜像流量合成 %d 条标准化测试用例，聚类去重率: %.2f%%",
        total_eval,
        len(synthesized_cases),
        dedup_ratio,
    )
    return report


def get_synthesis_report(report_id: str) -> SynthesisReport | None:
    """根据 ID 获取指定用例合成报告详情。"""
    return _SYNTHESIS_REPORTS.get(report_id)


def list_synthesis_reports() -> list[SynthesisReport]:
    """获取历史用例合成报告列表。"""
    reports = list(_SYNTHESIS_REPORTS.values())
    reports.sort(key=lambda r: r.created_at, reverse=True)
    return reports


def reset_synthesis_reports() -> None:
    """清空合成报告缓存。"""
    _SYNTHESIS_REPORTS.clear()
