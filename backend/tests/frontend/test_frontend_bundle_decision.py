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


def test_vite_keeps_ant_icons_split_and_bundle_threshold_visible(repo_file):
    config = repo_file("frontend/vite.config.ts")

    assert "if (id.includes('@ant-design/icons')) return 'ant-design-icons'" in config
    assert "if (id.includes('ant-design-vue')) return 'ant-design'" in config
    assert "chunkSizeWarningLimit: 1500" in config


def test_bundle_decision_records_decision_and_follow_up_trigger(repo_file):
    """决策文档只需记录结论与后续触发条件；具体字节数是历史快照，
    随依赖升级自然变化，不在测试里冻结。"""
    content = repo_file("docs/frontend-bundle-decision.md")

    assert "result: rejected" in content
    assert "build passed with no circular or large-chunk warning" in content
    assert "Ant Design Follow-Up Trigger" in content
    assert "gzip" in content
