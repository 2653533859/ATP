from app.core.otel import get_tracer
from app.core.tracing import attach_app_trace_id_to_current_span
from app.models.case import CaseType, RunStatus
from app.worker.dispatch import is_web_lowcode_config

_tracer = get_tracer("atp.dispatch")


async def dispatch_case(db, run, case, extra_vars: dict) -> bool:
    """根据 case_type 派发到对应 executor，并包一层 `executor.{type}` span。

    span attribute 携带 case_id/case_type/run_id 与 application trace_id，便于在
    Jaeger UI 中按业务标识反查。
    """
    case_type = case.case_type.value if hasattr(case.case_type, "value") else str(case.case_type)
    cfg = case.config or {}
    lowcode_suffix = ""
    if case.case_type in (CaseType.web, CaseType.android) and is_web_lowcode_config(cfg):
        lowcode_suffix = ".lowcode"

    span_name = f"executor.{case_type}{lowcode_suffix}"
    with _tracer.start_as_current_span(span_name) as span:
        case_id = getattr(case, "id", None)
        run_id = getattr(run, "id", None)
        environment = getattr(run, "environment", None)
        if case_id is not None:
            span.set_attribute("case.id", case_id)
        span.set_attribute("case.type", case_type)
        if run_id is not None:
            span.set_attribute("run.id", run_id)
        if environment:
            span.set_attribute("run.environment", str(environment))
        attach_app_trace_id_to_current_span(getattr(run, "trace_id", None))

        if case.case_type == CaseType.api:
            from app.worker.executors.api_executor import run_api_case

            await run_api_case(db, run, case, extra_vars)
            return True
        if case.case_type == CaseType.graphql:
            from app.worker.executors.graphql_executor import run_graphql_case

            await run_graphql_case(db, run, case, extra_vars)
            return True
        if case.case_type == CaseType.websocket:
            from app.worker.executors.websocket_executor import run_websocket_case

            await run_websocket_case(db, run, case, extra_vars)
            return True
        if case.case_type == CaseType.grpc:
            from app.worker.executors.grpc_executor import run_grpc_case

            await run_grpc_case(db, run, case, extra_vars)
            return True
        if case.case_type == CaseType.web:
            if is_web_lowcode_config(cfg):
                from app.worker.executors.web_lowcode_executor import run_web_lowcode

                await run_web_lowcode(db, run, case, extra_vars)
            else:
                from app.worker.executors.web_executor import run_web_case

                await run_web_case(db, run, case, extra_vars)
            return True
        if case.case_type == CaseType.android:
            if is_web_lowcode_config(cfg):
                from app.worker.executors.android_lowcode_executor import run_android_lowcode

                await run_android_lowcode(db, run, case, extra_vars)
            else:
                from app.worker.executors.android_executor import run_android_case

                await run_android_case(db, run, case, extra_vars)
            return True

        run.status = RunStatus.error
        run.error_message = f"执行器尚未实现: {case.case_type}"
        await db.commit()
        return False
