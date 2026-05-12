"""
Terminal Dock Widget

A thin QDockWidget wrapper for the terminal, following the same
pattern as the existing dock widgets in the plugin.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDockWidget, QTabWidget, QToolButton

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

        self._tabs = QTabWidget(self)
        self._tabs.setDocumentMode(True)
        self._tabs.setMovable(True)
        self._tabs.setTabsClosable(True)
        self._tabs.setTabPosition(QTabWidget.TabPosition.North)
        self._tabs.tabCloseRequested.connect(self.close_terminal)
        self._tabs.currentChanged.connect(self._focus_current_terminal)
        self._tabs.tabBar().tabMoved.connect(self._renumber_tabs)

        add_button = QToolButton(self)
        add_button.setText("+")
        add_button.setToolTip("New terminal")
        add_button.clicked.connect(self.add_terminal)
        self._tabs.setCornerWidget(add_button, Qt.Corner.TopRightCorner)

        self.setWidget(self._tabs)
        self.add_terminal()

    def add_terminal(self):
        """Create a new terminal tab and make it active."""
        terminal = TerminalWidget(iface=self.iface, parent=self._tabs)

        index = self._tabs.addTab(terminal, "Terminal")
        self._renumber_tabs()
        self._tabs.setCurrentIndex(index)
        terminal.focus_terminal()

    def close_terminal(self, index):
        """Close a terminal tab and shut down its shell process.

        Args:
            index: Tab index to close.
        """
        terminal = self._tabs.widget(index)
        if terminal is None:
            return

        self._tabs.removeTab(index)
        terminal.shutdown()
        terminal.deleteLater()

        if self._tabs.count() == 0:
            self.add_terminal()
        else:
            self._renumber_tabs()

    def _renumber_tabs(self, *_args):
        """Update tab labels to match the current visible terminal order."""
        for index in range(self._tabs.count()):
            self._tabs.setTabText(index, f"Terminal {index + 1}")

    def _focus_current_terminal(self, index):
        """Focus the terminal view in the active tab.

        Args:
            index: Active tab index.
        """
        terminal = self._tabs.widget(index)
        if terminal:
            terminal.focus_terminal()

    def shutdown(self):
        """Shut down the terminal cleanly."""
        while self._tabs.count():
            terminal = self._tabs.widget(0)
            self._tabs.removeTab(0)
            if terminal:
                terminal.shutdown()
                terminal.deleteLater()

    def closeEvent(self, event):
        """Handle dock widget close event.

        Args:
            event: QCloseEvent.
        """
        self.shutdown()
        event.accept()
