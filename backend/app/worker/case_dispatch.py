from app.models.case import CaseType, RunStatus
from app.worker.dispatch import is_web_lowcode_config


async def dispatch_case(db, run, case, extra_vars: dict) -> bool:
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
        cfg = case.config or {}
        if is_web_lowcode_config(cfg):
            from app.worker.executors.web_lowcode_executor import run_web_lowcode

            await run_web_lowcode(db, run, case, extra_vars)
        else:
            from app.worker.executors.web_executor import run_web_case

            await run_web_case(db, run, case, extra_vars)
        return True
    if case.case_type == CaseType.android:
        cfg = case.config or {}
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
