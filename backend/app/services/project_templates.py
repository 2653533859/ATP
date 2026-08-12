"""项目创建模板的静态资源定义。

模板只描述安全的基础结构，不包含环境密钥、成员、执行记录或外部资源。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectTemplateSpec:
    modules: tuple[str, ...] = ()
    environment_name: str | None = None
    dataset_name: str | None = None
    dataset_rows: tuple[dict[str, str], ...] = ()


PROJECT_TEMPLATE_SPECS: dict[str, ProjectTemplateSpec] = {
    "blank": ProjectTemplateSpec(),
    "api": ProjectTemplateSpec(
        modules=("接口测试", "接口认证"),
        environment_name="API 开发环境",
        dataset_name="API 示例数据",
        dataset_rows=({"user_id": "10001", "keyword": "demo"},),
    ),
    "web": ProjectTemplateSpec(
        modules=("页面功能", "页面回归"),
        environment_name="Web 测试环境",
        dataset_name="Web 示例数据",
        dataset_rows=({"username": "demo", "search_keyword": "ATP"},),
    ),
    "android": ProjectTemplateSpec(
        modules=("设备基础", "Android 回归"),
        environment_name="Android 测试环境",
        dataset_name="Android 示例数据",
        dataset_rows=({"device_label": "local-android", "package_name": "com.example.app"},),
    ),
    "full": ProjectTemplateSpec(
        modules=("接口测试", "Web UI 测试", "Android 测试"),
        environment_name="集成测试环境",
        dataset_name="全链路示例数据",
        dataset_rows=({"user_id": "10001", "username": "demo", "package_name": "com.example.app"},),
    ),
}


def get_project_template(template: str) -> ProjectTemplateSpec:
    """Return a template definition; callers should validate user input first."""

    return PROJECT_TEMPLATE_SPECS.get(template, PROJECT_TEMPLATE_SPECS["blank"])
