"""
seeds.py — Local convenience wrapper. Delegates to `flask seed` CLI command.
On Render, build.sh calls `FLASK_APP=wsgi.py flask seed` directly.
Locally, run either:  python seeds.py   OR   flask seed
"""
import os
import sys
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))

result = subprocess.run(
    [sys.executable, "-m", "flask", "seed"],
    env={**os.environ, "FLASK_APP": "wsgi.py", "PYTHONPATH": ROOT},
    cwd=ROOT,
)
sys.exit(result.returncode)
