#!/usr/bin/env python3
"""ATP 生产流量录制回放与契约防线通用集成 CLI 工具 (T4.3).

用法示例:
    python scripts/ci_atp_traffic_guard.py --endpoint "POST /api/v1/orders/checkout" --target-url "http://127.0.0.1:8000"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 将 backend 添加至 sys.path 以便导入核心业务模块
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.traffic_guard_pipeline_api import (  # noqa: E402
    execute_traffic_guard_pipeline,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ATP Traffic Guard & Contract Drift Gatekeeper CLI Tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default="POST /api/v1/orders/checkout",
        help="被测接口方法与端点路径 (如 POST /api/v1/orders/checkout)",
    )
    parser.add_argument(
        "--target-url",
        type=str,
        default="http://127.0.0.1:8000",
        help="影子回放目标服务 Base URL",
    )
    parser.add_argument(
        "--pipeline-name",
        type=str,
        default="ATP-Traffic-Guard-Pipeline",
        help="CI/CD 流水线作业标识",
    )
    parser.add_argument(
        "--write-guard",
        type=str,
        default="BLOCK_WRITES",
        choices=["BLOCK_WRITES", "SHADOW_HEADER_ONLY", "ALLOW_ALL", "DRY_RUN"],
        help="写操作安全防护模式",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=95.0,
        help="黄金响应基线最低相似度容差阈值 (%%)",
    )
    parser.add_argument(
        "--traffic-file",
        type=str,
        help="可选传入的生产捕获流量 JSON 数组文件路径",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        help="可选输出的结构化 JSON 报告文件路径",
    )
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="即使出现阻断或告警 (Exit Code 1/2)，也强制以 0 退出 (用于观察演练)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    # 1. 尝试读取外部流量文件
    traffic_samples = None
    if args.traffic_file:
        file_path = Path(args.traffic_file)
        if not file_path.is_file():
            print(f"[ERROR] 指定的流量数据文件不存在: {args.traffic_file}", file=sys.stderr)
            return 1
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                traffic_samples = json.load(f)
            if not isinstance(traffic_samples, list):
                print("[ERROR] 流量文件格式错误，必须为 JSON 列表", file=sys.stderr)
                return 1
        except Exception as exc:
            print(f"[ERROR] 读取流量数据文件解析失败: {exc}", file=sys.stderr)
            return 1

    # 2. 执行端到端生产流量防线四阶段检查点流水线
    try:
        report = execute_traffic_guard_pipeline(
            endpoint=args.endpoint,
            raw_traffic_samples=traffic_samples,
            target_base_url=args.target_url,
            pipeline_name=args.pipeline_name,
            write_guard_mode=args.write_guard,
            tolerance_threshold_pct=args.tolerance,
            simulate_chaos_resilience=True,
        )
    except Exception as exc:
        print(f"[FATAL] 执行流量防线流水线时发生未捕获异常: {exc}", file=sys.stderr)
        return 1

    # 3. 输出终端高对比度控制台日志
    print(report.console_log_output)

    # 4. 可选写出结构化 JSON 报告
    if args.output_json:
        out_path = Path(args.output_json)
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
            print(f"\n[INFO] 结构化流水线报告已持久化保存至: {out_path.resolve()}")
        except Exception as exc:
            print(f"\n[WARNING] 写出 JSON 报告失败: {exc}", file=sys.stderr)

    # 5. 退出码裁决
    if args.no_fail:
        print("\n[NOTICE] 已启用 --no-fail 宽松观察模式，强制退出码为 0")
        return 0

    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
