#!/usr/bin/env bash
set -e

# Render clones the repo to /opt/render/project/src/
# This script always runs with CWD = that directory (the project root).
# We set PYTHONPATH explicitly so every subsequent python/flask call
# can import the 'app' package without any sys.path tricks.

export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$(pwd)"

echo "==> Build dir  : $(pwd)"
echo "==> Python     : $(python --version)"
echo "==> PYTHONPATH : $PYTHONPATH"

echo "==> Installing dependencies..."
pip install -r requirements.txt

echo "==> Seeding database..."
FLASK_APP=wsgi.py flask seed

echo "==> Build complete ✓"
