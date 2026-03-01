#!/usr/bin/env bash
set -e

echo "==> Installing Python dependencies..."
pip install -r requirements.txt

echo "==> Seeding database..."
flask seed

echo "==> Build complete."
