"""Flask application factory for the athletics scoring web app.

Usage::

    from webapp import create_app
    app = create_app()

The factory wires configuration, the shared :class:`ScoringService`, the
download cache and the routes together.  Keeping construction in a factory makes
the app easy to configure differently in tests and production.
"""

from __future__ import annotations

import logging

from flask import Flask

from webapp.cache import ResultCache
from webapp.config import Config, config as default_config
from webapp.service import ScoringService

__all__ = ["create_app"]

_LOG = logging.getLogger("athletics.web")


def create_app(app_config: Config | None = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        app_config: Optional configuration override (defaults to env-driven
            :data:`webapp.config.config`).

    Returns:
        A ready-to-serve :class:`flask.Flask` instance.
    """
    cfg = app_config or default_config

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = cfg.max_upload_bytes
    app.config["SECRET_KEY"] = cfg.secret_key
    app.config["ASCORE"] = cfg

    # Shared, request-safe singletons (tables loaded once at startup).
    app.extensions["ascore_service"] = ScoringService()
    app.extensions["ascore_cache"] = ResultCache(cfg.result_ttl_seconds)

    from webapp.routes import bp as routes_bp

    app.register_blueprint(routes_bp)

    _LOG.info(
        "Athletics web app ready (edition %s, %s/%s events)",
        app.extensions["ascore_service"].tables_meta.get("edition", "?"),
        app.extensions["ascore_service"].tables_meta.get("event_count_men", "?"),
        app.extensions["ascore_service"].tables_meta.get("event_count_women", "?"),
    )
    return app
