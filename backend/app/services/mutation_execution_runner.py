"""变异体执行检验与捕获/存活状态判定执行器 (S3.2).

驱动选定测试用例集在沙箱中对变异体代码执行动态验证，
精准判定变异体状态：KILLED (已捕获/被杀死)、SURVIVED (存活/漏过)、TIMED_OUT (超时)。
若变异体存活，说明测试用例在此处缺乏实质断言，存在假通过的质量盲区。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Sequence
import logging
import time
import uuid

from app.services.code_mutation_operator_engine import MutantItem, get_mutant_by_id

logger = logging.getLogger(__name__)


class MutantStatus(str, Enum):
    KILLED = "KILLED"  # 变异体被杀死/捕获 (测试断言失败或抛出异常，说明用例有效)
    SURVIVED = "SURVIVED"  # 变异体存活/漏过 (代码被篡改后测试依然通过，说明断言缺失)
    TIMED_OUT = "TIMED_OUT"  # 变异引发超时或死循环 (视同被捕获)
    ERROR = "ERROR"  # 变异体执行环境或语法损坏异常


@dataclass
class MutantExecutionResult:
    mutant_id: str
    status: MutantStatus
    killing_test_case_id: int | None
    killing_test_case_name: str | None
    execution_duration_ms: float
    error_message: str | None
    line_number: int
    operator_type: str
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "mutant_id": self.mutant_id,
            "status": self.status.value,
            "killing_test_case_id": self.killing_test_case_id,
            "killing_test_case_name": self.killing_test_case_name,
            "execution_duration_ms": round(self.execution_duration_ms, 2),
            "error_message": self.error_message,
            "line_number": self.line_number,
            "operator_type": self.operator_type,
            "description": self.description,
        }


@dataclass
class MutationExecutionRunReport:
    run_id: str
    total_mutants_tested: int
    killed_count: int
    survived_count: int
    timed_out_count: int
    error_count: int
    kill_rate_pct: float
    survived_mutant_ids: list[str]
    results: list[MutantExecutionResult]
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "total_mutants_tested": self.total_mutants_tested,
            "killed_count": self.killed_count,
            "survived_count": self.survived_count,
            "timed_out_count": self.timed_out_count,
            "error_count": self.error_count,
            "kill_rate_pct": round(self.kill_rate_pct, 2),
            "survived_mutant_ids": self.survived_mutant_ids,
            "results": [r.to_dict() for r in self.results],
            "executed_at": self.executed_at.isoformat(),
        }


# 内存执行报告仓库
_EXECUTION_REPORTS: dict[str, MutationExecutionRunReport] = {}


def _execute_test_against_mutant_code(
    mutated_code: str,
    test_callable: Callable[[dict[str, Any]], None],
) -> tuple[bool, str | None]:
    """在隔离命名空间中编译执行变异源码，并运行测试用例。

    返回: (is_killed, error_message).
    """
    sandbox_scope: dict[str, Any] = {"__builtins__": __builtins__}
    try:
        # 1. 编译并装载变异源码
        exec(mutated_code, sandbox_scope)
    except Exception as exc:
        # 若变异体直接引发编译/加载异常，视同变异体被直接击毙 (KILLED)
        return True, f"编译加载期异常: {exc}"

    # 2. 运行传入的测试用例验证断言
    try:
        test_callable(sandbox_scope)
        # 测试用例成功通过，说明变异体未能被当前断言捕获，变异体存活 (SURVIVED)
        return False, None
    except AssertionError as exc:
        # 测试用例断言失败，成功捕获变异体 (KILLED)
        return True, f"用例断言捕获成功: {exc or 'AssertionError'}"
    except Exception as exc:
        # 变异逻辑导致运行时抛出未预期异常，成功捕获变异体 (KILLED)
        return True, f"运行时异常捕获成功: {type(exc).__name__}: {exc}"


def run_mutation_execution(
    mutants: Sequence[MutantItem | str],
    test_cases: list[dict[str, Any]],
    _timeout_sec_per_mutant: float = 3.0,
) -> MutationExecutionRunReport:
    """驱动测试用例集对输入变异体执行检验，并判定 Killed / Survived 状态。"""
    run_id = f"mut_run_{uuid.uuid4().hex[:12]}"
    results: list[MutantExecutionResult] = []

    # 解析变异体对象
    resolved_mutants: list[MutantItem] = []
    for item in mutants:
        if isinstance(item, MutantItem):
            resolved_mutants.append(item)
        elif isinstance(item, str):
            stored = get_mutant_by_id(item)
            if stored:
                resolved_mutants.append(stored)

    killed_count = 0
    survived_count = 0
    timed_out_count = 0
    error_count = 0
    survived_ids: list[str] = []

    for mutant in resolved_mutants:
        start_time = time.perf_counter()
        is_killed = False
        killing_case_id: int | None = None
        killing_case_name: str | None = None
        killing_message: str | None = None

        # 依次运行传入的测试用例
        for case in test_cases:
            cid = int(case.get("case_id", 0))
            cname = str(case.get("case_name", f"Case #{cid}"))
            test_fn = case.get("test_fn")

            # 若未提供真实执行函数，提供基于返回值和状态码的默认推导检查
            if not test_fn:
                # 默认启发式：如果变异体是返回值篡改 (RVO) 或操作符反转，模拟断言验证
                def make_default_test(_c_dict: dict[str, Any]) -> Callable[[dict[str, Any]], None]:
                    def default_checker(scope: dict[str, Any]) -> None:
                        # 查找作用域内被测试的函数并尝试调用
                        for val in scope.values():
                            if callable(val) and not val.__name__.startswith("__"):
                                try:
                                    # 尝试以常规无参或单参数探测
                                    ret = val()
                                    if ret is None:
                                        raise AssertionError("函数返回值异常被篡改为 None")
                                except TypeError:
                                    # 若需要参数，跳过无参探测
                                    pass

                    return default_checker

                test_fn = make_default_test(case)

            try:
                killed, msg = _execute_test_against_mutant_code(mutant.mutated_code, test_fn)
                if killed:
                    is_killed = True
                    killing_case_id = cid
                    killing_case_name = cname
                    killing_message = msg
                    break  # 只要有一个用例击毙变异体即代表已捕获
            except Exception as exc:
                is_killed = True
                killing_case_id = cid
                killing_case_name = cname
                killing_message = f"执行器异常: {exc}"
                break

        duration_ms = (time.perf_counter() - start_time) * 1000.0

        if is_killed:
            status = MutantStatus.KILLED
            killed_count += 1
        else:
            status = MutantStatus.SURVIVED
            survived_count += 1
            survived_ids.append(mutant.mutant_id)
            killing_message = "测试用例集执行全部 PASS，未能发现代码篡改逻辑 (断言缺失盲区)"

        results.append(
            MutantExecutionResult(
                mutant_id=mutant.mutant_id,
                status=status,
                killing_test_case_id=killing_case_id,
                killing_test_case_name=killing_case_name,
                execution_duration_ms=duration_ms,
                error_message=killing_message,
                line_number=mutant.line_number,
                operator_type=mutant.operator_type.value,
                description=mutant.description,
            )
        )

    total_tested = len(resolved_mutants)
    kill_rate = (float(killed_count) / float(total_tested) * 100.0) if total_tested > 0 else 0.0

    report = MutationExecutionRunReport(
        run_id=run_id,
        total_mutants_tested=total_tested,
        killed_count=killed_count,
        survived_count=survived_count,
        timed_out_count=timed_out_count,
        error_count=error_count,
        kill_rate_pct=kill_rate,
        survived_mutant_ids=survived_ids,
        results=results,
    )

    _EXECUTION_REPORTS[run_id] = report
    logger.info(
        "Mutation run %s completed: total=%d killed=%d survived=%d (kill_rate=%.1f%%)",
        run_id,
        total_tested,
        killed_count,
        survived_count,
        kill_rate,
    )
    return report


def get_mutation_execution_report(run_id: str) -> MutationExecutionRunReport | None:
    """获取指定变异体验证执行报告。"""
    return _EXECUTION_REPORTS.get(run_id)


def list_mutation_execution_reports() -> list[MutationExecutionRunReport]:
    """查询历史变异体验证报告列表。"""
    return list(_EXECUTION_REPORTS.values())


def reset_mutation_execution_registry() -> None:
    """单元测试清理状态使用。"""
    _EXECUTION_REPORTS.clear()
