#!/usr/bin/env bash
set -e

echo "==> Installing dependencies..."
pip install -r requirements.txt

echo "==> Seeding database..."
# Use the venv python directly — avoids all flask CLI / PYTHONPATH issues.
# seeds.py sets its own sys.path from __file__ before any imports.
python seeds.py

echo "==> Build complete."
