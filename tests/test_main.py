"""Tests for main app factory."""


from solomon.main import create_app


def test_create_app():
    app = create_app()
    assert app.title == "Solomon"
    # Verify routers are registered by checking routes
    routes = [r.path for r in app.routes]
    assert "/api/health" in routes
    assert "/api/session" in routes
    assert "/api/skills" in routes
    assert "/api/chat" in routes
