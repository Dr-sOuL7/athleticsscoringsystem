"""Vercel serverless entry point.

Vercel's Python runtime (``@vercel/python``) serves the WSGI ``app`` exported
here; every route is handled by the existing Flask application.  See
``vercel.json`` for request routing and which non-Python files are bundled into
the function.

The app is intentionally created at import time so the 2.3 MB scoring table is
parsed once per warm instance (kept out of the per-request path).
"""

from __future__ import annotations

import sys
from pathlib import Path

# When Vercel imports this file, make the project root importable so the
# ``webapp`` and ``athletics_scoring`` packages (and the bundled ``data/`` and
# ``examples/`` files they resolve by relative path) are found.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from webapp import create_app  # noqa: E402  (after sys.path setup)

app = create_app()
