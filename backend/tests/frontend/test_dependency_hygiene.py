"""依赖卫生契约（Q13-06）：allowScripts 白名单与文档一致，覆盖所有已知
带 install script 的传递依赖，防止未审脚本悄悄溜入。"""

import json


def test_allow_scripts_covers_known_install_script_packages(repo_root):
    package_json = json.loads((repo_root / "frontend" / "package.json").read_text(encoding="utf-8"))
    allow_scripts = package_json.get("allowScripts", {})

    # 这三个是当前依赖树中带 install/postinstall 脚本的传递依赖，
    # 各自用途与安全评估见 docs/dependency-hygiene.md。
    for pkg in ("core-js", "fsevents", "vue-demi"):
        assert allow_scripts.get(pkg) is True, f"{pkg} 缺少 allowScripts 审批"


def test_dependency_hygiene_doc_records_each_allowlisted_package(repo_file):
    content = repo_file("docs/dependency-hygiene.md")
    for marker in ("fsevents", "core-js", "vue-demi", "npm ci", "0 vulnerabilities", "Refresh Policy"):
        assert marker in content


def test_frontend_overrides_pin_supported_versions(repo_root):
    package_json = json.loads((repo_root / "frontend" / "package.json").read_text(encoding="utf-8"))
    overrides = package_json.get("overrides", {})

    # Q12-03 遗留：glob 强制到受支持的 v13，vue-i18n 主依赖已升到 v11。
    assert overrides.get("glob", "").startswith("^13")
    assert package_json["dependencies"]["vue-i18n"].startswith("^11")
