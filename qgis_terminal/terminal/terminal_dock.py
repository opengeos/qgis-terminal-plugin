"""
Terminal Dock Widget

A thin QDockWidget wrapper for the terminal, following the same
pattern as the existing dock widgets in the plugin.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDockWidget

from .terminal_widget import TerminalWidget


class TerminalDockWidget(QDockWidget):
    """Dockable terminal panel for QGIS."""

    def __init__(self, iface, parent=None):
        """Initialize the terminal dock widget.

        Args:
            iface: QGIS interface instance.
            parent: Parent widget.
        """
        super().__init__("Terminal", parent)
        self.iface = iface

        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)

        self._terminal_widget = TerminalWidget(iface=iface, parent=self)
        self.setWidget(self._terminal_widget)

    def shutdown(self):
        """Shut down the terminal cleanly."""
        if self._terminal_widget:
            self._terminal_widget.shutdown()

    def closeEvent(self, event):
        """Handle dock widget close event.

        Args:
            event: QCloseEvent.
        """
        self.shutdown()
        event.accept()
