def load_all_models() -> None:
    """Import every mapped model so SQLAlchemy metadata is complete before use."""
    from app.models.user import User, UserRole
    from app.models.project import Project, Module
    from app.models.case import TestCase, TestRun, StepResult, CaseSnapshot
    from app.models.environment import Environment, EnvVariable
    from app.models.device import Device
    from app.models.apk import Apk
    from app.models.suite import TestSuite, SuiteRun
    from app.models.notification import NotificationConfig
    from app.models.mock import MockRule
    from app.models.bug_tracker import BugTracker
    from app.models.audit import AuditLog
    from app.models.plan import TestPlan, PlanRun

    _ = (
        User,
        UserRole,
        Project,
        Module,
        TestCase,
        TestRun,
        StepResult,
        CaseSnapshot,
        Environment,
        EnvVariable,
        Device,
        Apk,
        TestSuite,
        SuiteRun,
        NotificationConfig,
        MockRule,
        BugTracker,
        AuditLog,
        TestPlan,
        PlanRun,
    )
