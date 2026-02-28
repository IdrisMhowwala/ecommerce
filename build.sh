#!/usr/bin/env bash
set -e

echo "==> Installing Python dependencies..."
pip install -r requirements.txt

echo "==> Seeding database..."
python seeds.py

echo "==> Build complete."
