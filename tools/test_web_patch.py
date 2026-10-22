#!/usr/bin/env python3
"""Run the KeyStep Con page's firmware patcher (tests/fwpatch.js) on Arturia's stock 2.5.20 file in headless Chrome and
check its output is byte for byte the KSCON build. Usage: test_web_patch.py <page dir> (CHROME = browser binary).
This tool never contacts or writes to a device."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from build_ksp_patch import PATCH_BUILD, PATCH_VERSION
from build_names_patch import KSPF, ROOT

page = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "web").resolve()
built = (ROOT / f"firmware/patched/KSCON_2.5.{PATCH_VERSION}_build{PATCH_BUILD}.kspf").read_bytes()
with tempfile.TemporaryDirectory() as tmp:
    script = Path(tmp) / "fwpatch.js"
    script.write_text(f'const STOCK_B64="{base64.b64encode(KSPF.read_bytes()).decode()}";\n' + (page / "tests/fwpatch.js").read_text())
    run = subprocess.run(["node", str(page / "tests/cdp.mjs"), f"file://{page}/keystep-interactive-manual.html", str(script)],
                         capture_output=True, text=True, env={**os.environ, "TIMEOUT": "120000"}, check=True).stdout
if "ERRORS:" not in run:
    sys.exit("no result from the page:\n" + run[-2000:])
res = json.loads(run[:run.rindex("ERRORS:")])
got = res.pop("outSha", "")
res["output equals the built .kspf"] = "ok" if got == hashlib.sha256(built).hexdigest() else f"FAIL ({got})"
bad = {k: v for k, v in res.items() if v != "ok"}
print(f"{len(res) - len(bad)} ok" + "".join(f"\n{k}: {v}" for k, v in bad.items()) + "\n" + run[run.rindex("ERRORS:"):].strip())
sys.exit(1 if bad or "ERRORS: none" not in run else 0)
