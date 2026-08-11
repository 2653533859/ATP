from app.models.bootstrap import load_all_models
from app.models.mobile_special import (
    MobileIncident,
    MobileMetricSample,
    MobileRunArtifact,
    MobileSpecialRun,
    MobileSpecialTask,
)


load_all_models()


def test_mobile_special_enum_names_match_the_alembic_schema():
    assert MobileSpecialTask.__table__.c.task_type.type.name == "task_type"
    assert MobileSpecialTask.__table__.c.source_type.type.name == "source_type"
    assert MobileSpecialTask.__table__.c.device_scope_type.type.name == "device_scope_type"
    assert MobileSpecialRun.__table__.c.task_type.type.name == "task_type"
    assert MobileSpecialRun.__table__.c.status.type.name == "run_status"
    assert MobileSpecialRun.__table__.c.trigger_type.type.name == "trigger_type"
    assert MobileMetricSample.__table__.c.metric_type.type.name == "metric_type"
    assert MobileIncident.__table__.c.incident_type.type.name == "incident_type"
    assert MobileRunArtifact.__table__.c.artifact_type.type.name == "artifact_type"
