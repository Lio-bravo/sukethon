import json
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("args,code,status", [([], 0, "complete"),
    (["--fail", "grasp"], 0, "complete"),
    (["--fail", "transfer"], 2, "stopped"),
    (["--placement-offset", "0.02"], 2, "stopped")])
def test_module_entry_point(args, code, status):
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, "-m", "sukethon.cli", "dry-run"] + args,
                            cwd=root, capture_output=True, text=True, timeout=10)
    assert result.returncode == code, result.stderr
    report = json.loads(result.stdout)
    assert report["status"] == status
    assert report["validation_scope"] == "synthetic_logic_only"
