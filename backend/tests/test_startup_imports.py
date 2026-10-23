"""API start-up must not import heavy, rarely used libraries.

yfinance pulls in pandas/numpy (~1.3 s) and was imported at app start purely
because a router imported the price provider. These libraries must be loaded
lazily, inside the code paths that use them.
"""

import json
import subprocess
import sys
from pathlib import Path

HEAVY_MODULES = ("yfinance", "pandas", "numpy", "requests", "pdfplumber", "camelot")


def test_app_import_does_not_load_heavy_libraries() -> None:
    probe = (
        "import json, sys; import app.main; "
        f"print(json.dumps({{m: m in sys.modules for m in {HEAVY_MODULES!r}}}))"
    )
    out = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    loaded = json.loads(out.stdout.strip().splitlines()[-1])
    assert not any(loaded.values()), f"heavy modules loaded at app import: {loaded}"
