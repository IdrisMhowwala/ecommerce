"""
wsgi.py — The single entry point for both Gunicorn and the Flask CLI.

Having this at the project root means:
  - gunicorn wsgi:app            ← always finds 'app' object
  - FLASK_APP=wsgi.py flask seed ← always finds CLI commands
  - python wsgi.py               ← runs dev server locally

No PYTHONPATH manipulation needed because wsgi.py IS at the project root,
so Python's import system can always find the 'app' package next to it.
"""
import os
import sys

# Belt-and-suspenders: ensure the directory containing this file
# (the project root) is on sys.path before anything is imported.
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app   # noqa: E402  (import after path fix)

application = create_app()   # WSGI name expected by some servers
app = application            # Gunicorn default name

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_ENV") == "development",
    )
