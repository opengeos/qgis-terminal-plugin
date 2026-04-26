"""
Terminal Widget

Container widget with toolbar and terminal view. Manages the shell
process lifecycle and wires up signals between components.
"""

import os
import sys

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QPushButton,
    QToolButton,
    QSizePolicy,
)
from qgis.PyQt.QtGui import QIcon

from .shell_process import create_shell_process, get_available_shells, get_default_shell
from .terminal_view import TerminalView


class TerminalWidget(QWidget):
    """Container widget with toolbar and terminal view."""

    def __init__(self, iface=None, parent=None):
        """Initialize the terminal widget.

        Args:
            iface: QGIS interface instance (optional).
            parent: Parent widget.
        """
        super().__init__(parent)
        self._iface = iface
        self._shell_process = None
        self._setup_ui()
        self._start_shell()

    def _setup_ui(self):
        """Set up the widget layout and components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(4, 2, 4, 2)
        toolbar.setSpacing(4)

        # Shell selector
        self._shell_combo = QComboBox()
        self._shell_combo.setMinimumWidth(100)
        self._shell_combo.setMaximumWidth(200)
        shells = get_available_shells()
        for name, path in shells:
            self._shell_combo.addItem(name, path)
        # Select the default shell
        default = get_default_shell()
        for i in range(self._shell_combo.count()):
            if self._shell_combo.itemData(i) == default:
                self._shell_combo.setCurrentIndex(i)
                break
        toolbar.addWidget(self._shell_combo)

        toolbar.addStretch()

        # Clear button
        clear_btn = QToolButton()
        clear_btn.setText("Clear")
        clear_btn.setToolTip("Clear terminal output")
        clear_btn.clicked.connect(self._clear_terminal)
        toolbar.addWidget(clear_btn)

        # Restart button
        restart_btn = QToolButton()
        restart_btn.setText("Restart")
        restart_btn.setToolTip("Restart the shell")
        restart_btn.clicked.connect(self.restart_shell)
        toolbar.addWidget(restart_btn)

        toolbar_widget = QWidget()
        toolbar_widget.setLayout(toolbar)
        toolbar_widget.setStyleSheet(
            "QWidget { background-color: #252526; }"
            "QComboBox { background-color: #3c3c3c; color: #d4d4d4; "
            "border: 1px solid #555; padding: 2px 4px; }"
            "QToolButton { background-color: #3c3c3c; color: #d4d4d4; "
            "border: 1px solid #555; padding: 2px 8px; }"
            "QToolButton:hover { background-color: #4c4c4c; }"
        )
        layout.addWidget(toolbar_widget)

        # Terminal view
        self._terminal_view = TerminalView(self)
        self._terminal_view.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        layout.addWidget(self._terminal_view)

        # Connect signals
        self._terminal_view.input_ready.connect(self._on_input)
        self._terminal_view.resize_requested.connect(self._on_resize)

    def _get_initial_cwd(self):
        """Get the initial working directory for the shell.

        Returns:
            Path string for the initial working directory.
        """
        # Try QGIS project directory first
        if self._iface:
            try:
                from qgis.core import QgsProject

                project_home = QgsProject.instance().homePath()
                if project_home and os.path.isdir(project_home):
                    return project_home
            except Exception:  # nosec B110
                # If QgsProject is unavailable or has no project loaded,
                # silently fall back to the user's home directory below.
                pass
        return os.path.expanduser("~")

    def _start_shell(self):
        """Start a new shell process."""
        shell_path = self._shell_combo.currentData()
        if not shell_path:
            shell_path = get_default_shell()

        cwd = self._get_initial_cwd()

        self._shell_process = create_shell_process(self)
        self._shell_process.output_ready.connect(self._terminal_view.append_output)
        self._shell_process.process_exited.connect(self._on_process_exited)
        self._shell_process.start(shell_path, cwd=cwd)

        # Send initial resize
        self._terminal_view._emit_resize()

    def _on_input(self, data):
        """Forward input from the terminal view to the shell.

        Args:
            data: Bytes from user input.
        """
        if self._shell_process and self._shell_process.is_running():
            self._shell_process.write(data)

    def _on_resize(self, rows, cols):
        """Forward resize events to the shell.

        Args:
            rows: Number of rows.
            cols: Number of columns.
        """
        if self._shell_process:
            self._shell_process.resize(rows, cols)

    def _on_process_exited(self, exit_code):
        """Handle shell process exit.

        Args:
            exit_code: Process exit code.
        """
        self._terminal_view.append_output(
            f"\r\n[Process exited with code {exit_code}]\r\n"
        )

    def _clear_terminal(self):
        """Clear the terminal display."""
        self._terminal_view.reset()

    def restart_shell(self):
        """Kill the current shell and start a new one."""
        if self._shell_process:
            self._shell_process.terminate()
            self._shell_process = None

        self._terminal_view.reset()
        self._start_shell()

    def shutdown(self):
        """Shut down the shell process cleanly."""
        if self._shell_process:
            self._shell_process.terminate()
            self._shell_process = None
