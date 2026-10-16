#!/usr/bin/env python3
"""ATP CI/CD 流水线 Checkpoint 检查点通用集成 CLI 命令行工具 (S4.3).

用法示例:
    python scripts/ci_atp_checkpoint.py --pr-id 1024 --commit-sha a1b2c3d4 --diff-file /tmp/pr.diff
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# 将 backend 添加至 sys.path 以加载核心服务
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.ci_pipeline_checkpoint_api import (  # noqa: E402
    execute_ci_pipeline_checkpoint,
)
from app.services.smart_test_selection_engine import SelectionStrategy  # noqa: E402


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ATP CI/CD Pipeline Checkpoint Gatekeeper CLI Tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--diff-file", type=str, help="Git Unified Diff 文件路径")
    parser.add_argument("--diff-text", type=str, help="直接传入的 Diff 补丁文本")
    parser.add_argument("--pipeline-name", type=str, default="CI-Pipeline-Worker", help="流水线名称")
    parser.add_argument("--commit-sha", type=str, default="HEAD", help="当前待测 Commit SHA")
    parser.add_argument("--pr-id", type=str, default="0", help="Pull Request / Merge Request 编号")
    parser.add_argument("--author", type=str, default="ci-bot", help="提交者或 PR 作者")
    parser.add_argument("--target-branch", type=str, default="main", help="目标合流主干分支")
    parser.add_argument(
        "--strategy",
        type=str,
        default="balanced",
        choices=["minimal", "balanced", "comprehensive"],
        help="精准测试推荐策略",
    )
    parser.add_argument("--test-pass-rate", type=float, default=100.0, help="测试用例通过率 (%%)")
    parser.add_argument("--test-failed-cases", type=int, default=0, help="失败用例数")
    parser.add_argument("--mutation-score", type=float, default=85.0, help="代码变异得分 (%%)")
    parser.add_argument("--has-dual-approvals", action="store_true", help="是否具备极高危变更双人签批")
    parser.add_argument("--output-json", type=str, help="可选输出的 JSON 结构化报告文件路径")
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="即使门禁阻断也强制以退出码 0 退出 (不阻断 CI)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    # 读取 Diff 文本
    diff_content = ""
    if args.diff_file and os.path.exists(args.diff_file):
        diff_content = Path(args.diff_file).read_text(encoding="utf-8", errors="replace")
    elif args.diff_text:
        diff_content = args.diff_text
    else:
        # 默认无输入时生成微型局部占位 diff
        diff_content = (
            "diff --git a/app/main.py b/app/main.py\n"
            "--- a/app/main.py\n"
            "+++ b/app/main.py\n"
            "@@ -1,2 +1,2 @@\n"
            "-# v1\n"
            "+# v2\n"
        )

    strategy_enum = SelectionStrategy(args.strategy.lower())

    report = execute_ci_pipeline_checkpoint(
        diff_text=diff_content,
        pipeline_name=args.pipeline_name,
        commit_sha=args.commit_sha,
        pr_id=args.pr_id,
        author=args.author,
        target_branch=args.target_branch,
        selection_strategy=strategy_enum,
        mock_test_pass_rate_pct=args.test_pass_rate,
        mock_test_failed_cases_count=args.test_failed_cases,
        mutation_score_pct=args.mutation_score,
        has_dual_approvals=args.has_dual_approvals,
    )

    # 打印格式化终端控制台日志
    print(report.console_log_output)

    # 可选导出结构化 JSON 报告
    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[ATP Checkpoint] 结构化报告已导出至: {out_path.resolve()}")

    if args.no_fail:
        return 0
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
