"""Entry point to run the athletics scoring web application.

Examples::

    python run_web.py                 # serve on http://127.0.0.1:8000 (waitress)
    python run_web.py --port 5000     # choose a port
    python run_web.py --debug         # Flask dev server with auto-reload
    python run_web.py --host 0.0.0.0  # expose on the local network

For production, a WSGI server is used (waitress — cross-platform).  The Flask
development server (``--debug``) should only be used while developing.
"""

from __future__ import annotations

import argparse
import logging

from webapp import create_app
from webapp.logging_bootstrap import configure_web_logging


def main() -> None:
    """Parse arguments and start the server."""
    parser = argparse.ArgumentParser(description="Run the Athletics Meet Scorer web app.")
    parser.add_argument("--host", default="127.0.0.1", help="Interface to bind (default 127.0.0.1).")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default 8000).")
    parser.add_argument("--debug", action="store_true", help="Use the Flask dev server with auto-reload.")
    args = parser.parse_args()

    configure_web_logging()
    app = create_app()

    if args.debug:
        app.run(host=args.host, port=args.port, debug=True)
        return

    from waitress import serve

    logging.getLogger("athletics.web").info(
        "Serving on http://%s:%d  (press Ctrl+C to stop)", args.host, args.port
    )
    serve(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
