"""Run the control plane (API + controller + self-healing monitor).

    python scripts/devrun.py     # then open http://localhost:8097
"""
from __future__ import annotations

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print("starting deployment controller…  dashboard → http://localhost:8097  (Ctrl+C to stop)")
subprocess.run([sys.executable, "-m", "app", "api"], cwd=ROOT)
