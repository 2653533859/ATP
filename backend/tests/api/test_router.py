def test_api_v1_router_registers_core_and_recent_resource_routes():
    from app.api.v1.router import router

    paths = {
        f"{included.include_context.prefix}{route.path}"
        for included in router.routes
        for route in included.original_router.routes
        if getattr(route, "path", None)
    }

    assert "/api/v1/auth/login" in paths
    assert "/api/v1/projects" in paths
    assert "/api/v1/web-recordings" in paths
    assert "/api/v1/projects/{project_id}/api-contract-assets" in paths
    assert "/api/v1/users" in paths
    assert "/api/v1/configuration-center/overview" in paths
    assert "/api/v1/configuration-center/revisions/{revision_id}/diff" in paths
