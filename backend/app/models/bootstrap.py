def load_all_models() -> None:
    """Import every mapped model so SQLAlchemy metadata is complete before use."""
    from app.models.user import User, UserRole
    from app.models.project import Project, Module
    from app.models.case import TestCase, CaseStep, TestRun, StepResult, CaseSnapshot
    from app.models.environment import Environment, EnvVariable
    from app.models.device import Device
    from app.models.apk import Apk
    from app.models.suite import TestSuite, SuiteRun
    from app.models.notification import NotificationConfig
    from app.models.mock import MockRule
    from app.models.mock_snapshot import MockRuleSnapshot
    from app.models.bug_tracker import BugTracker
    from app.models.audit import AuditLog
    from app.models.plan import TestPlan, PlanRun
    from app.models.mobile_special import (
        MobileSpecialTask,
        MobileSpecialRun,
        MobileMetricSample,
        MobileIncident,
        MobileRunArtifact,
    )
    from app.models.global_variable import GlobalVariable
    from app.models.storage_policy import StoragePolicy
    from app.models.ai_llm_config import AILLMConfig
    from app.models.dataset import TestDataset, TestDatasetVersion
    from app.models.user_project import UserProject, ProjectRole
    from app.models.dashboard_alert import DashboardAlertRule, DashboardAlertEvent
    from app.models.healing_feedback import HealingFeedbackAggregate
    from app.models.healing_prompt_example import HealingPromptExample
    from app.models.user_setting import UserSetting
    from app.models.performance import PerformanceTest, PerformanceRun

    _ = (
        User,
        UserRole,
        Project,
        Module,
        TestCase,
        CaseStep,
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
        MockRuleSnapshot,
        BugTracker,
        AuditLog,
        TestPlan,
        PlanRun,
        MobileSpecialTask,
        MobileSpecialRun,
        MobileMetricSample,
        MobileIncident,
        MobileRunArtifact,
        GlobalVariable,
        StoragePolicy,
        AILLMConfig,
        TestDataset,
        TestDatasetVersion,
        UserProject,
        ProjectRole,
        DashboardAlertRule,
        DashboardAlertEvent,
        HealingFeedbackAggregate,
        HealingPromptExample,
        UserSetting,
        PerformanceTest,
        PerformanceRun,
    )
