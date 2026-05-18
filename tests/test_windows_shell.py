"""Smoke test for the Windows ConPTY-backed shell process.

Runs on ``windows-latest`` in CI to verify that ``WindowsShellProcess``
can spawn ``cmd.exe`` through pywinpty, deliver keystrokes, and surface
output back to the Qt event loop. Skipped on other platforms.
"""

import os
import sys
import time

import pytest

if sys.platform != "win32":
    pytest.skip("Windows-only smoke test", allow_module_level=True)

# Headless Qt before any QApplication is touched.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Bail with a clear skip message if pywinpty isn't installed in the runner.
pytest.importorskip("winpty")

from qgis.PyQt.QtWidgets import QApplication  # noqa: E402

from qgis_terminal.terminal.shell_process import WindowsShellProcess  # noqa: E402

_APP = None


def _get_app():
    """Return the current QApplication or create one.

    Returns:
        QApplication instance.
    """
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def _drain_until(predicate, timeout=10.0, tick=0.05):
    """Spin the Qt event loop until ``predicate()`` is true or timeout.

    Args:
        predicate: Zero-arg callable returning truthy when the wait is done.
        timeout: Maximum seconds to wait.
        tick: Sleep interval between event-loop ticks.

    Returns:
        True if the predicate became true before the timeout.
    """
    deadline = time.monotonic() + timeout
    app = _get_app()
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(tick)
    app.processEvents()
    return predicate()


def test_windows_shell_echoes_via_conpty():
    """cmd.exe under ConPTY echoes ``hello`` back through ``output_ready``."""
    _get_app()
    captured = []

    proc = WindowsShellProcess()
    proc.output_ready.connect(captured.append)

    try:
        proc.start(os.environ.get("COMSPEC", "cmd.exe"))
        assert _drain_until(lambda: len(captured) > 0, timeout=10.0), (
            "no output received from cmd.exe within timeout"
        )
        proc.write(b"echo hello\r\n")
        assert _drain_until(
            lambda: "hello" in "".join(captured), timeout=10.0
        ), f"'hello' not found in output; captured={captured!r}"
    finally:
        proc.terminate()
