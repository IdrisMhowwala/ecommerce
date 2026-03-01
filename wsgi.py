"""
wsgi.py — entry point for Gunicorn (production) and local dev.

Usage:
  Production:  gunicorn wsgi:app
  Local:       python wsgi.py
"""
import os
import sys

# Ensure the project root is on sys.path so 'app' package is always found
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_ENV", "development") == "development",
    )
