"""Tests for the terminal dock tab manager."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.PyQt.QtWidgets import QApplication, QWidget

from qgis_terminal.terminal import terminal_dock

_APP = None


class FakeTerminalWidget(QWidget):
    """Minimal terminal widget used to avoid spawning shell processes."""

    instances = []

    def __init__(self, iface=None, parent=None):
        """Initialize the fake widget.

        Args:
            iface: QGIS interface instance.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.iface = iface
        self.focus_count = 0
        self.shutdown_count = 0
        FakeTerminalWidget.instances.append(self)

    def focus_terminal(self):
        """Record that the terminal view would receive focus."""
        self.focus_count += 1

    def shutdown(self):
        """Record that the shell process would be shut down."""
        self.shutdown_count += 1


def _get_app():
    """Return the current QApplication or create one for widget tests.

    Returns:
        QApplication instance.
    """
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def test_terminal_dock_adds_and_closes_terminal_tabs(monkeypatch):
    """Verify terminal tabs can be added and closed independently."""
    _get_app()
    FakeTerminalWidget.instances = []
    monkeypatch.setattr(terminal_dock, "TerminalWidget", FakeTerminalWidget)

    dock = terminal_dock.TerminalDockWidget(iface=None)
    assert dock._tabs.count() == 1

    first = FakeTerminalWidget.instances[0]
    dock.add_terminal()

    assert dock._tabs.count() == 2
    assert dock._tabs.currentIndex() == 1
    assert dock._tabs.tabText(0) == "Terminal 1"
    assert dock._tabs.tabText(1) == "Terminal 2"
    assert FakeTerminalWidget.instances[-1].focus_count >= 1

    dock.close_terminal(0)

    assert dock._tabs.count() == 1
    assert dock._tabs.tabText(0) == "Terminal 1"
    assert first.shutdown_count == 1

    dock.shutdown()
    assert dock._tabs.count() == 0


def test_closing_last_terminal_creates_replacement(monkeypatch):
    """Verify the dock keeps one usable terminal available."""
    _get_app()
    FakeTerminalWidget.instances = []
    monkeypatch.setattr(terminal_dock, "TerminalWidget", FakeTerminalWidget)

    dock = terminal_dock.TerminalDockWidget(iface=None)
    first = FakeTerminalWidget.instances[0]

    dock.close_terminal(0)

    assert dock._tabs.count() == 1
    assert first.shutdown_count == 1
    assert FakeTerminalWidget.instances[-1] is not first
    assert dock._tabs.tabText(0) == "Terminal 1"


def test_terminal_labels_reuse_visible_order_after_close(monkeypatch):
    """Verify new terminal labels do not keep increasing after closures."""
    _get_app()
    FakeTerminalWidget.instances = []
    monkeypatch.setattr(terminal_dock, "TerminalWidget", FakeTerminalWidget)

    dock = terminal_dock.TerminalDockWidget(iface=None)
    dock.add_terminal()
    dock.add_terminal()

    dock.close_terminal(1)
    dock.add_terminal()

    labels = [dock._tabs.tabText(index) for index in range(dock._tabs.count())]
    assert labels == ["Terminal 1", "Terminal 2", "Terminal 3"]
