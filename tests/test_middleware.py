"""Tests for error handler middleware."""

from solomon.middleware.error_handler import ErrorHandlerMiddleware


def test_error_handler_middleware_exists():
    """Verify the middleware class exists and inherits correctly."""
    from starlette.middleware.base import BaseHTTPMiddleware
    assert issubclass(ErrorHandlerMiddleware, BaseHTTPMiddleware)
