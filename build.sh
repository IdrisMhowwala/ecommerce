#!/usr/bin/env bash
set -e

# Always run from the directory this script lives in (project root).
# Render sets the working directory to the repo root, but being explicit
# prevents any edge-case surprises.
cd "$(dirname "$0")"

echo "==> Working directory: $(pwd)"
echo "==> Python: $(python --version)"

echo "==> Installing Python dependencies..."
pip install -r requirements.txt

echo "==> Seeding database..."
python seeds.py

echo "==> Build complete."
