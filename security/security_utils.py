"""Security helpers: auth, API key checks, rate limiting, and secure headers."""

from __future__ import annotations

import functools
import os
from typing import Any, Callable

from flask import Flask, jsonify, redirect, request, session, url_for

try:
    from flask_wtf.csrf import CSRFProtect
except Exception:  # pragma: no cover - optional dependency
    CSRFProtect = None

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except Exception:  # pragma: no cover - optional dependency
    Limiter = None
    get_remote_address = None

try:
    from flask_talisman import Talisman
except Exception:  # pragma: no cover - optional dependency
    Talisman = None


def setup_security(app: Flask) -> dict[str, Any]:
    """Initialize optional security extensions with safe fallbacks."""
    components: dict[str, Any] = {}

    csrf = None
    if CSRFProtect is not None:
        csrf = CSRFProtect(app)
    components["csrf"] = csrf

    limiter = None
    if Limiter is not None and get_remote_address is not None:
        limiter = Limiter(key_func=get_remote_address, app=app, default_limits=["120 per minute"])
    components["limiter"] = limiter

    if Talisman is not None:
        Talisman(
            app,
            force_https=False,
            content_security_policy={
                "default-src": ["'self'"],
                "img-src": ["'self'", "data:"],
                "script-src": ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"],
                "style-src": ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com"],
                "font-src": ["'self'", "https://cdnjs.cloudflare.com"],
            },
        )

    @app.after_request
    def _secure_headers(response):
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        return response

    return components


def auth_required_enabled() -> bool:
    """Check whether session auth is enabled."""
    return os.environ.get("AUTH_REQUIRED", "false").lower() in {"1", "true", "yes"}


def get_users() -> dict[str, dict[str, str]]:
    """Load configured users for role-based access checks."""
    return {
        os.environ.get("ADMIN_USER", "admin"): {
            "password": os.environ.get("ADMIN_PASSWORD", "admin123"),
            "role": "admin",
        },
        os.environ.get("ANALYST_USER", "analyst"): {
            "password": os.environ.get("ANALYST_PASSWORD", "analyst123"),
            "role": "analyst",
        },
    }


def authenticate_user(username: str, password: str) -> dict[str, str] | None:
    """Validate credentials against configured in-memory users."""
    users = get_users()
    profile = users.get(username)
    if profile and profile["password"] == password:
        return {"username": username, "role": profile["role"]}
    return None


def role_required(required_roles: set[str] | None = None):
    """Decorator enforcing optional role-based access policy."""
    required_roles = required_roles or {"admin", "analyst"}

    def decorator(fn: Callable[..., Any]):
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any):
            if not auth_required_enabled():
                return fn(*args, **kwargs)

            role = session.get("role")
            if not role:
                if request.path.startswith("/api"):
                    return jsonify({"ok": False, "error": "Authentication required"}), 401
                return redirect(url_for("index"))
            if role not in required_roles:
                if request.path.startswith("/api"):
                    return jsonify({"ok": False, "error": "Insufficient role"}), 403
                return redirect(url_for("index"))
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def api_key_required(fn: Callable[..., Any]):
    """Decorator for optional API key enforcement on API endpoints."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any):
        expected = os.environ.get("API_KEY", "")
        if expected:
            # Allow authenticated UI session users without explicit API key header.
            if session.get("role"):
                return fn(*args, **kwargs)
            supplied = request.headers.get("X-API-Key", "")
            if supplied != expected:
                return jsonify({"ok": False, "error": "Invalid API key"}), 401
        return fn(*args, **kwargs)

    return wrapper
