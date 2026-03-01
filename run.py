"""run.py — Local development entry point. Use wsgi.py for production."""
import os
import sys

# Ensure project root is on path (needed when run as 'python run.py')
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_ENV", "development") == "development",
    )
