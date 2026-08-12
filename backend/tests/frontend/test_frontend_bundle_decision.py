def _frontend_sources(repo_root):
    for path in (repo_root / "frontend" / "src").rglob("*"):
        if path.suffix in {".ts", ".vue"} and path.is_file():
            yield path


def test_frontend_has_no_full_echarts_runtime_import(repo_root):
    """全量 `import * as echarts from 'echarts'` 会让按需引入（echarts/core + use）失效。"""
    offenders = [
        str(path.relative_to(repo_root))
        for path in _frontend_sources(repo_root)
        if "import * as echarts" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_echarts_registration_is_centralized_in_chart_theme(repo_root, repo_file):
    chart_theme = repo_file("frontend/src/utils/chartTheme.ts")
    assert "from 'echarts/core'" in chart_theme
    assert "use([" in chart_theme

    # 视图不再各自 use([...])——注册出口唯一，避免漏注册组件导致图表静默渲染失败
    offenders = [
        str(path.relative_to(repo_root))
        for path in (repo_root / "frontend" / "src" / "views").rglob("*.vue")
        if "use([" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_vite_splits_antd_across_routes_with_icons_isolated(repo_file):
    config = repo_file("frontend/vite.config.ts")

    # icons 仍独立成 chunk；ant-design-vue 组件不再归入单体 chunk（Q13-04 路由级分裂）
    assert "if (id.includes('@ant-design/icons')) return 'ant-design-icons'" in config
    assert "return 'ant-design'" not in config
    # 单体移除后最大 chunk 是 echarts；告警阈值收紧以更早发现回归
    assert "chunkSizeWarningLimit: 600" in config


def test_vite_config_resolves_alias_in_esm_and_runner_loaders(repo_file):
    config = repo_file("frontend/vite.config.ts")

    assert "fileURLToPath(import.meta.url)" in config
    assert "const __dirname = dirname(fileURLToPath(import.meta.url))" in config


def test_bundle_decision_records_route_split_decision(repo_file):
    """决策文档记录结论、证据要点与后续触发条件；具体字节数是历史快照，不在测试里冻结。"""
    content = repo_file("docs/frontend-bundle-decision.md")

    assert "Ant Design Follow-Up Trigger" in content
    assert "gzip" in content
    # Q13-04 决策：路由级分裂被采纳（go），/login 首屏显著下降
    assert "result: adopted" in content
    assert "route-level" in content.lower()
