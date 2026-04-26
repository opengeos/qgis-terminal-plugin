"""
Terminal View Widget

A QPlainTextEdit subclass that provides terminal display and input handling.
Uses a ScreenBuffer for proper VT100 terminal emulation. All user keystrokes
are forwarded to the shell process; the pty handles echo, line editing, and
history. The screen buffer is rendered to the widget after each output batch.
"""

import sys

from qgis.PyQt.QtCore import Qt, pyqtSignal, QTimer
from qgis.PyQt.QtGui import (
    QColor,
    QFont,
    QTextCursor,
    QTextCharFormat,
    QPalette,
    QKeySequence,
)
from qgis.PyQt.QtWidgets import QPlainTextEdit, QApplication, QMenu, QAction

from .screen_buffer import ScreenBuffer, DEFAULT_BG, DEFAULT_FG


def _get_default_font():
    """Get a platform-appropriate monospace font.

    Returns:
        QFont configured for terminal display.
    """
    if sys.platform == "darwin":
        family = "Menlo"
    elif sys.platform == "win32":
        family = "Consolas"
    else:
        family = "Monospace"

    font = QFont(family, 11)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFixedPitch(True)
    return font


class TerminalView(QPlainTextEdit):
    """Terminal display and input widget.

    Displays terminal output using a virtual screen buffer for proper
    escape sequence handling. Forwards all keyboard input to the shell.
    """

    input_ready = pyqtSignal(bytes)
    resize_requested = pyqtSignal(int, int)

    def __init__(self, parent=None):
        """Initialize the terminal view.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self._screen = ScreenBuffer(24, 80)
        self._setup_appearance()

        # Do NOT use setReadOnly(True) -- it causes Qt to swallow
        # Enter, Tab, Backspace before keyPressEvent fires.
        # Instead we prevent editing by never calling super().keyPressEvent().
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setUndoRedoEnabled(False)

        # Prevent Tab from changing focus to another widget
        self.setTabChangesFocus(False)

        # Accept focus so we receive key events
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Batch rendering with a short timer to avoid re-rendering
        # on every single byte of output
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(16)  # ~60fps
        self._render_timer.timeout.connect(self._render_screen)

        # Track whether user has scrolled up
        self._auto_scroll = True
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def _setup_appearance(self):
        """Configure the terminal appearance."""
        font = _get_default_font()
        self.setFont(font)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(DEFAULT_BG))
        palette.setColor(QPalette.ColorRole.Text, QColor(DEFAULT_FG))
        self.setPalette(palette)

        self.setStyleSheet(
            f"QPlainTextEdit {{ "
            f"background-color: {DEFAULT_BG}; "
            f"color: {DEFAULT_FG}; "
            f"selection-background-color: #264f78; "
            f"selection-color: #ffffff; "
            f"border: none; "
            f"}}"
        )

    def keyPressEvent(self, event):
        """Handle key press events by forwarding to the shell.

        Args:
            event: QKeyEvent.
        """
        key = event.key()
        modifiers = event.modifiers()
        text = event.text()

        # Ctrl+Shift combinations
        if modifiers == (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            if key == Qt.Key.Key_C:
                self.copy()
                return
            if key == Qt.Key.Key_V:
                self._paste_from_clipboard()
                return

        # Ctrl+C: copy if selection, otherwise send SIGINT
        if key == Qt.Key.Key_C and modifiers == Qt.KeyboardModifier.ControlModifier:
            if self.textCursor().hasSelection():
                self.copy()
            else:
                self.input_ready.emit(b"\x03")
            return

        # Ctrl+V: paste
        if key == Qt.Key.Key_V and modifiers == Qt.KeyboardModifier.ControlModifier:
            self._paste_from_clipboard()
            return

        # Ctrl+A: select all
        if key == Qt.Key.Key_A and modifiers == Qt.KeyboardModifier.ControlModifier:
            self.selectAll()
            return

        # Ctrl+L: clear screen
        if key == Qt.Key.Key_L and modifiers == Qt.KeyboardModifier.ControlModifier:
            self.input_ready.emit(b"\x0c")
            return

        # Ctrl+D: EOF
        if key == Qt.Key.Key_D and modifiers == Qt.KeyboardModifier.ControlModifier:
            self.input_ready.emit(b"\x04")
            return

        # Ctrl+Z: suspend (Unix only)
        if key == Qt.Key.Key_Z and modifiers == Qt.KeyboardModifier.ControlModifier:
            if sys.platform != "win32":
                self.input_ready.emit(b"\x1a")
            return

        # Enter/Return -- send CR (\r), not LF (\n).
        # Real terminals always send CR for Enter. In canonical mode the
        # pty driver converts CR->NL (ICRNL), but interactive programs
        # using raw mode expect CR directly.
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.input_ready.emit(b"\r")
            return

        # Backspace
        if key == Qt.Key.Key_Backspace:
            self.input_ready.emit(b"\x7f")
            return

        # Tab
        if key == Qt.Key.Key_Tab:
            self.input_ready.emit(b"\t")
            return

        # Arrow keys
        if key == Qt.Key.Key_Up:
            self.input_ready.emit(b"\x1b[A")
            return
        if key == Qt.Key.Key_Down:
            self.input_ready.emit(b"\x1b[B")
            return
        if key == Qt.Key.Key_Right:
            self.input_ready.emit(b"\x1b[C")
            return
        if key == Qt.Key.Key_Left:
            self.input_ready.emit(b"\x1b[D")
            return

        # Home/End
        if key == Qt.Key.Key_Home:
            self.input_ready.emit(b"\x1b[H")
            return
        if key == Qt.Key.Key_End:
            self.input_ready.emit(b"\x1b[F")
            return

        # Delete
        if key == Qt.Key.Key_Delete:
            self.input_ready.emit(b"\x1b[3~")
            return

        # Page Up/Down: scroll the view
        if key == Qt.Key.Key_PageUp:
            sb = self.verticalScrollBar()
            sb.setValue(
                sb.value() - self.viewport().height() // self.fontMetrics().height()
            )
            return
        if key == Qt.Key.Key_PageDown:
            sb = self.verticalScrollBar()
            sb.setValue(
                sb.value() + self.viewport().height() // self.fontMetrics().height()
            )
            return

        # Escape
        if key == Qt.Key.Key_Escape:
            self.input_ready.emit(b"\x1b")
            return

        # Regular text input
        if text and not modifiers & Qt.KeyboardModifier.ControlModifier:
            self.input_ready.emit(text.encode("utf-8"))
            return

        # Catch-all: do NOT call super().keyPressEvent() -- that would
        # allow QPlainTextEdit to edit the document directly.
        event.accept()

    def insertFromMimeData(self, source):
        """Handle paste/drag-drop by sending to the shell instead of editing.

        Args:
            source: QMimeData with the pasted content.
        """
        if source.hasText():
            self.input_ready.emit(source.text().encode("utf-8"))

    def inputMethodEvent(self, event):
        """Handle input method (IME) events for CJK etc.

        Args:
            event: QInputMethodEvent.
        """
        commit = event.commitString()
        if commit:
            self.input_ready.emit(commit.encode("utf-8"))
        # Do not call super -- prevent direct document editing
        event.accept()

    def append_output(self, data):
        """Process terminal output through the screen buffer.

        Args:
            data: Raw string from the shell process.
        """
        self._screen.feed(data)
        # Schedule a render (batches rapid output)
        if not self._render_timer.isActive():
            self._render_timer.start()

    def _render_screen(self):
        """Render the screen buffer contents to the text widget."""
        # When in alternate screen mode (vim, less, Claude Code, etc.),
        # only show the alternate screen -- no scrollback from the main buffer.
        if self._screen._using_alt:
            scrollback = []
        else:
            scrollback = self._screen.get_scrollback_lines()
        screen = self._screen.get_lines()

        # Build the full document
        self.setUpdatesEnabled(False)
        cursor = QTextCursor(self.document())
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.removeSelectedText()

        cursor.movePosition(QTextCursor.MoveOperation.Start)

        all_lines = scrollback + screen
        for line_idx, runs in enumerate(all_lines):
            if line_idx > 0:
                cursor.insertBlock()
            for text, attrs in runs:
                fmt = attrs.to_format()
                cursor.insertText(text, fmt)

        self.setUpdatesEnabled(True)

        # Auto-scroll to bottom
        if self._auto_scroll:
            sb = self.verticalScrollBar()
            sb.setValue(sb.maximum())

        self._screen.changed = False

    def _on_scroll(self, value):
        """Track whether the user has scrolled away from the bottom.

        Args:
            value: Current scrollbar value.
        """
        sb = self.verticalScrollBar()
        self._auto_scroll = value >= sb.maximum() - 3

    def resizeEvent(self, event):
        """Handle widget resize to update terminal dimensions.

        Args:
            event: QResizeEvent.
        """
        super().resizeEvent(event)
        self._emit_resize()

    def _emit_resize(self):
        """Calculate and emit terminal dimensions, resize screen buffer."""
        fm = self.fontMetrics()
        char_width = fm.averageCharWidth()
        char_height = fm.height()

        if char_width > 0 and char_height > 0:
            viewport = self.viewport()
            cols = max(viewport.width() // char_width, 1)
            rows = max(viewport.height() // char_height, 1)
            self._screen.resize(rows, cols)
            self.resize_requested.emit(rows, cols)

    def contextMenuEvent(self, event):
        """Show a context menu with terminal actions.

        Args:
            event: QContextMenuEvent.
        """
        menu = QMenu(self)

        copy_action = QAction("Copy", self)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_action.setEnabled(self.textCursor().hasSelection())
        copy_action.triggered.connect(self.copy)
        menu.addAction(copy_action)

        paste_action = QAction("Paste", self)
        paste_action.setShortcut(QKeySequence.StandardKey.Paste)
        paste_action.triggered.connect(self._paste_from_clipboard)
        menu.addAction(paste_action)

        menu.addSeparator()

        clear_action = QAction("Clear", self)
        clear_action.triggered.connect(self._clear_terminal)
        menu.addAction(clear_action)

        select_all_action = QAction("Select All", self)
        select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        select_all_action.triggered.connect(self.selectAll)
        menu.addAction(select_all_action)

        menu.exec(event.globalPos())

    def _paste_from_clipboard(self):
        """Paste clipboard contents to the shell."""
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if text:
            self.input_ready.emit(text.encode("utf-8"))

    def _clear_terminal(self):
        """Clear the terminal display and screen buffer."""
        self._screen.reset()
        self.clear()

    def reset(self):
        """Reset the screen buffer and display."""
        self._screen.reset()
        self.clear()
