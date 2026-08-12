"""项目配置导入导出辅助逻辑。

传输文件是配置快照，不是数据库备份：敏感值只保留脱敏标记，运行记录和外部资源不进入快照。
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Literal, cast

from app.models.ai_llm_config import AILLMConfig
from app.models.dataset import TestDataset
from app.models.environment import Environment, EnvVariable
from app.models.project import Module, Project
from app.services.dataset_storage import rows_from_source
from app.schemas.project import (
    ProjectExportPayload,
    ProjectTransferAIModel,
    ProjectTransferDataset,
    ProjectTransferEnvironment,
    ProjectTransferModule,
    ProjectTransferProject,
    ProjectTransferVariable,
)

REDACTED_VALUE = "[REDACTED]"
_SENSITIVE_KEY_RE = re.compile(
    r"(?:password|passwd|secret|token|cookie|authorization|api[_-]?key|access[_-]?key|private[_-]?key)",
    re.IGNORECASE,
)


def _is_sensitive_key(key: str | None) -> bool:
    return bool(key and _SENSITIVE_KEY_RE.search(key))


def sanitize_json_value(value: Any, key: str | None = None) -> Any:
    if _is_sensitive_key(key):
        return REDACTED_VALUE
    if isinstance(value, dict):
        return {str(item_key): sanitize_json_value(item_value, str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, list):
        return [sanitize_json_value(item) for item in value]
    return value


def build_project_export(
    project: Project,
    modules: list[Module],
    environments: list[Environment],
    variables: list[EnvVariable],
    datasets: list[TestDataset],
    ai_model: AILLMConfig | None,
) -> ProjectExportPayload:
    variables_by_environment: dict[int, list[ProjectTransferVariable]] = defaultdict(list)
    has_redacted_value = False
    for variable in variables:
        redacted = bool(variable.is_secret) or _is_sensitive_key(variable.key)
        if redacted:
            has_redacted_value = True
        variables_by_environment[variable.env_id].append(
            ProjectTransferVariable(
                key=variable.key,
                value=None if redacted else variable.value,
                is_secret=bool(variable.is_secret),
                redacted=redacted,
            )
        )

    export_environments = [
        ProjectTransferEnvironment(
            name=environment.name,
            description=environment.description,
            variables=variables_by_environment.get(environment.id, []),
        )
        for environment in environments
    ]
    export_datasets = [
        ProjectTransferDataset(
            name=dataset.name,
            description=dataset.description,
            format=cast(Literal["csv", "json"], dataset.format if dataset.format in {"csv", "json"} else "json"),
            storage_mode=cast(Literal["database", "minio"], getattr(dataset, "storage_mode", None) or "database"),
            rows=[sanitize_json_value(row) for row in rows_from_source(dataset)],
            schema_fields=[sanitize_json_value(field) for field in (dataset.schema_fields or [])],
            validation_policy=cast(
                Literal["soft", "hard"],
                dataset.validation_policy if dataset.validation_policy in {"soft", "hard"} else "soft",
            ),
        )
        for dataset in datasets
    ]
    warnings = [
        "敏感环境变量和数据集字段已脱敏，导入后请重新填写。" if has_redacted_value else "",
        "AI 模型只导出非敏感元数据，API Key 不会进入文件。" if ai_model else "",
    ]
    return ProjectExportPayload(
        exported_at=datetime.now(timezone.utc),
        project=ProjectTransferProject(
            name=project.name,
            project_code=project.project_code,
            description=project.description,
            run_retention_days_override=project.run_retention_days_override,
            ai_model=(
                ProjectTransferAIModel(
                    name=ai_model.name,
                    provider=ai_model.provider,
                    model_name=ai_model.model_name,
                    supports_vision=bool(ai_model.supports_vision),
                )
                if ai_model
                else None
            ),
        ),
        modules=[
            ProjectTransferModule(
                id=module.id,
                name=module.name,
                module_code=module.module_code,
                parent_id=module.parent_id,
                sort_order=module.sort_order,
            )
            for module in modules
        ],
        environments=export_environments,
        datasets=export_datasets,
        warnings=[warning for warning in warnings if warning],
    )
