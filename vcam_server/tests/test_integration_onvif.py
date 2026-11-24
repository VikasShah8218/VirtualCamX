"""Runs tools/onvif_smoke.py against a running server.

    set VCAM_IT=192.168.1.17:8005   (camera host:port)  then  pytest -m integration
"""
import os
import subprocess
import sys

import pytest

TARGET = os.environ.get("VCAM_IT")


@pytest.mark.integration
@pytest.mark.skipif(not TARGET, reason="set VCAM_IT=host:port of a running virtual camera")
def test_onvif_smoke():
    host, port = TARGET.split(":")
    tool = os.path.join(os.path.dirname(__file__), "..", "tools", "onvif_smoke.py")
    r = subprocess.run([sys.executable, tool, host, port], capture_output=True, text=True, timeout=300)
    print(r.stdout)
    assert r.returncode == 0, r.stdout[-2000:]
