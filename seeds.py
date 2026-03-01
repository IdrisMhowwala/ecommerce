"""
seeds.py — Local convenience wrapper around `flask seed`.

On Render:  flask seed  (called by build.sh — no import path issues)
Locally:    python seeds.py  OR  flask seed
"""
import subprocess
import sys

if __name__ == "__main__":
    result = subprocess.run(
        [sys.executable, "-m", "flask", "seed"],
        env={**__import__("os").environ, "FLASK_APP": "run.py"},
    )
    sys.exit(result.returncode)
