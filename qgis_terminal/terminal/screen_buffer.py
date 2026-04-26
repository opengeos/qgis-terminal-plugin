"""
Virtual Terminal Screen Buffer

Maintains a 2D grid of character cells with cursor position tracking.
Handles VT100/ANSI escape sequences for cursor movement, erasing,
scrolling, and text attributes. The rendered screen state can be
read by the terminal view widget for display.
"""

import re
from dataclasses import dataclass, field

from qgis.PyQt.QtGui import QColor, QFont, QTextCharFormat

# VS Code-inspired dark theme color palette (indices 0-15)
PALETTE_16 = [
    "#1e1e1e",  # 0: black
    "#f44747",  # 1: red
    "#6a9955",  # 2: green
    "#dcdcaa",  # 3: yellow
    "#569cd6",  # 4: blue
    "#c586c0",  # 5: magenta
    "#4ec9b0",  # 6: cyan
    "#d4d4d4",  # 7: white
    "#808080",  # 8: bright black
    "#f44747",  # 9: bright red
    "#6a9955",  # 10: bright green
    "#dcdcaa",  # 11: bright yellow
    "#9cdcfe",  # 12: bright blue
    "#c586c0",  # 13: bright magenta
    "#4ec9b0",  # 14: bright cyan
    "#ffffff",  # 15: bright white
]

DEFAULT_FG = "#d4d4d4"
DEFAULT_BG = "#1e1e1e"


def _build_256_palette():
    """Build full 256-color palette as hex strings."""
    table = list(PALETTE_16)
    # 16-231: 6x6x6 color cube
    for r in range(6):
        for g in range(6):
            for b in range(6):
                rv = 55 + 40 * r if r else 0
                gv = 55 + 40 * g if g else 0
                bv = 55 + 40 * b if b else 0
                table.append(f"#{rv:02x}{gv:02x}{bv:02x}")
    # 232-255: grayscale
    for i in range(24):
        v = 8 + 10 * i
        table.append(f"#{v:02x}{v:02x}{v:02x}")
    return table


_PALETTE_256 = _build_256_palette()


@dataclass
class CellAttrs:
    """Text attributes for a single cell."""

    fg: str = DEFAULT_FG
    bg: str = DEFAULT_BG
    bold: bool = False
    italic: bool = False
    underline: bool = False
    reverse: bool = False

    def copy(self):
        """Return a shallow copy."""
        return CellAttrs(
            fg=self.fg,
            bg=self.bg,
            bold=self.bold,
            italic=self.italic,
            underline=self.underline,
            reverse=self.reverse,
        )

    def to_format(self):
        """Convert to QTextCharFormat.

        Returns:
            QTextCharFormat with these attributes applied.
        """
        fmt = QTextCharFormat()
        fg = self.bg if self.reverse else self.fg
        bg = self.fg if self.reverse else self.bg
        fmt.setForeground(QColor(fg))
        fmt.setBackground(QColor(bg))
        if self.bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        if self.italic:
            fmt.setFontItalic(True)
        if self.underline:
            fmt.setFontUnderline(True)
        return fmt

    def __eq__(self, other):
        if not isinstance(other, CellAttrs):
            return False
        return (
            self.fg == other.fg
            and self.bg == other.bg
            and self.bold == other.bold
            and self.italic == other.italic
            and self.underline == other.underline
            and self.reverse == other.reverse
        )


@dataclass
class Cell:
    """A single character cell on the screen."""

    char: str = " "
    attrs: CellAttrs = field(default_factory=CellAttrs)


# Regex patterns
# CSI parameters can include digits, semicolons, and modifier prefixes
# like ? (DEC private), > (extended), < (kitty), = (alternate).
_CSI_RE = re.compile(r"\x1b\[([0-9;?<>=]*)([A-Za-z@`])")
_OSC_RE = re.compile(r"\x1b\].*?(?:\x07|\x1b\\)")
_ANY_ESC_RE = re.compile(
    r"\x1b(?:"
    r"\[([0-9;?<>=]*)([A-Za-z@`])"  # CSI (with >, <, = modifiers)
    r"|\].*?(?:\x07|\x1b\\)"  # OSC
    r"|[()][0-9A-Za-z]"  # Character set
    r"|[=>MNOP78#]"  # Simple escapes
    r")"
)


class ScreenBuffer:
    """Virtual terminal screen buffer.

    Maintains a 2D grid of character cells and processes VT100/ANSI
    escape sequences to update the grid, cursor position, and attributes.
    """

    def __init__(self, rows=24, cols=80):
        """Initialize the screen buffer.

        Args:
            rows: Number of rows.
            cols: Number of columns.
        """
        self.rows = rows
        self.cols = cols
        self.cursor_row = 0
        self.cursor_col = 0
        self._attrs = CellAttrs()
        self._dirty_lines = set()
        self._scrollback = []
        self._max_scrollback = 10000

        # The screen grid
        self._grid = []
        for _ in range(rows):
            self._grid.append(self._empty_line())

        # Alternate screen buffer (for programs like vim, less)
        self._alt_grid = None
        self._alt_cursor = None
        self._using_alt = False

        # Scroll region (top, bottom) -- inclusive
        self._scroll_top = 0
        self._scroll_bottom = rows - 1

        # Saved cursor
        self._saved_cursor = (0, 0)
        self._saved_attrs = CellAttrs()

        # Track if content changed
        self.changed = True

    def _empty_line(self):
        """Create an empty line of cells.

        Returns:
            List of Cell objects.
        """
        return [Cell(" ", CellAttrs()) for _ in range(self.cols)]

    def resize(self, rows, cols):
        """Resize the screen buffer.

        Args:
            rows: New number of rows.
            cols: New number of columns.
        """
        if rows == self.rows and cols == self.cols:
            return

        old_rows = self.rows
        old_cols = self.cols
        self.rows = rows
        self.cols = cols
        self._scroll_bottom = rows - 1

        # Adjust grid rows
        while len(self._grid) < rows:
            self._grid.append(self._empty_line())
        while len(self._grid) > rows:
            self._grid.pop()

        # Adjust grid cols
        for i, line in enumerate(self._grid):
            if len(line) < cols:
                line.extend(Cell(" ", CellAttrs()) for _ in range(cols - len(line)))
            elif len(line) > cols:
                self._grid[i] = line[:cols]

        # Clamp cursor
        self.cursor_row = min(self.cursor_row, rows - 1)
        self.cursor_col = min(self.cursor_col, cols - 1)

        self._dirty_lines = set(range(rows))
        self.changed = True

    def feed(self, data):
        """Process terminal output data.

        Args:
            data: String of terminal output to process.
        """
        pos = 0
        length = len(data)

        while pos < length:
            ch = data[pos]

            if ch == "\x1b":
                m = _ANY_ESC_RE.match(data, pos)
                if m:
                    if m.group(1) is not None or m.group(2) is not None:
                        # CSI sequence
                        self._handle_csi(m.group(1) or "", m.group(2) or "")
                    # OSC and other sequences silently consumed
                    pos = m.end()
                else:
                    # Incomplete or unknown escape -- skip ESC
                    pos += 1
            elif ch == "\r":
                self.cursor_col = 0
                pos += 1
            elif ch == "\n":
                self._line_feed()
                pos += 1
            elif ch == "\x08":
                # Backspace
                if self.cursor_col > 0:
                    self.cursor_col -= 1
                pos += 1
            elif ch == "\x07":
                # Bell -- ignore
                pos += 1
            elif ch == "\t":
                # Tab -- advance to next 8-col tab stop
                next_tab = ((self.cursor_col // 8) + 1) * 8
                self.cursor_col = min(next_tab, self.cols - 1)
                pos += 1
            elif ch >= " " or ch not in "\x00\x01\x02\x03\x04\x05\x06\x0e\x0f":
                # Printable character
                self._put_char(ch)
                pos += 1
            else:
                # Other control characters -- skip
                pos += 1

        self.changed = True

    def _put_char(self, ch):
        """Write a character at the current cursor position.

        Args:
            ch: Character to write.
        """
        if self.cursor_col >= self.cols:
            # Auto-wrap
            self.cursor_col = 0
            self._line_feed()

        row = self.cursor_row
        col = self.cursor_col
        self._grid[row][col] = Cell(ch, self._attrs.copy())
        self._dirty_lines.add(row)
        self.cursor_col += 1

    def _line_feed(self):
        """Move cursor down one line, scrolling if necessary."""
        if self.cursor_row == self._scroll_bottom:
            self._scroll_up(1)
        elif self.cursor_row < self.rows - 1:
            self.cursor_row += 1

    def _scroll_up(self, count=1):
        """Scroll the screen up within the scroll region.

        Args:
            count: Number of lines to scroll.
        """
        for _ in range(count):
            # Save line going to scrollback (only if scroll region is full screen)
            if self._scroll_top == 0 and not self._using_alt:
                line_text = "".join(
                    c.char for c in self._grid[self._scroll_top]
                ).rstrip()
                if line_text or self._scrollback:
                    self._scrollback.append(self._grid[self._scroll_top])
                    if len(self._scrollback) > self._max_scrollback:
                        self._scrollback.pop(0)

            # Shift lines up within scroll region
            for r in range(self._scroll_top, self._scroll_bottom):
                self._grid[r] = self._grid[r + 1]
            self._grid[self._scroll_bottom] = self._empty_line()

        self._dirty_lines = set(range(self.rows))

    def _scroll_down(self, count=1):
        """Scroll the screen down within the scroll region.

        Args:
            count: Number of lines to scroll.
        """
        for _ in range(count):
            for r in range(self._scroll_bottom, self._scroll_top, -1):
                self._grid[r] = self._grid[r - 1]
            self._grid[self._scroll_top] = self._empty_line()
        self._dirty_lines = set(range(self.rows))

    def _handle_csi(self, params_str, cmd):
        """Handle a CSI escape sequence.

        Args:
            params_str: Parameter string (numbers separated by semicolons).
            cmd: Command character.
        """
        # Parse params -- strip modifier prefixes (?, >, <, =)
        params = []
        for p in params_str.split(";"):
            p = p.strip("?><= ")
            if p:
                try:
                    params.append(int(p))
                except ValueError:
                    params.append(0)
            else:
                params.append(0)
        if not params:
            params = [0]

        if cmd == "m":
            self._handle_sgr(params)
        elif cmd == "H" or cmd == "f":
            # Cursor position
            row = max(params[0] if params else 1, 1) - 1
            col = max(params[1] if len(params) > 1 else 1, 1) - 1
            self.cursor_row = min(row, self.rows - 1)
            self.cursor_col = min(col, self.cols - 1)
        elif cmd == "A":
            # Cursor up
            n = max(params[0], 1)
            self.cursor_row = max(self.cursor_row - n, self._scroll_top)
        elif cmd == "B":
            # Cursor down
            n = max(params[0], 1)
            self.cursor_row = min(self.cursor_row + n, self._scroll_bottom)
        elif cmd == "C":
            # Cursor forward (right)
            n = max(params[0], 1)
            self.cursor_col = min(self.cursor_col + n, self.cols - 1)
        elif cmd == "D":
            # Cursor backward (left)
            n = max(params[0], 1)
            self.cursor_col = max(self.cursor_col - n, 0)
        elif cmd == "E":
            # Cursor next line
            n = max(params[0], 1)
            self.cursor_row = min(self.cursor_row + n, self._scroll_bottom)
            self.cursor_col = 0
        elif cmd == "F":
            # Cursor previous line
            n = max(params[0], 1)
            self.cursor_row = max(self.cursor_row - n, self._scroll_top)
            self.cursor_col = 0
        elif cmd == "G":
            # Cursor horizontal absolute
            col = max(params[0], 1) - 1
            self.cursor_col = min(col, self.cols - 1)
        elif cmd == "J":
            self._handle_erase_display(params[0])
        elif cmd == "K":
            self._handle_erase_line(params[0])
        elif cmd == "L":
            # Insert lines
            n = max(params[0], 1)
            self._insert_lines(n)
        elif cmd == "M":
            # Delete lines
            n = max(params[0], 1)
            self._delete_lines(n)
        elif cmd == "P":
            # Delete characters
            n = max(params[0], 1)
            self._delete_chars(n)
        elif cmd == "@":
            # Insert characters
            n = max(params[0], 1)
            self._insert_chars(n)
        elif cmd == "S":
            # Scroll up
            n = max(params[0], 1)
            self._scroll_up(n)
        elif cmd == "T":
            # Scroll down
            n = max(params[0], 1)
            self._scroll_down(n)
        elif cmd == "d":
            # Vertical position absolute
            row = max(params[0], 1) - 1
            self.cursor_row = min(row, self.rows - 1)
        elif cmd == "r":
            # Set scroll region
            top = max(params[0] if params else 1, 1) - 1
            bottom = (params[1] if len(params) > 1 and params[1] else self.rows) - 1
            self._scroll_top = min(top, self.rows - 1)
            self._scroll_bottom = min(bottom, self.rows - 1)
            self.cursor_row = self._scroll_top
            self.cursor_col = 0
        elif cmd == "s":
            # Save cursor position
            self._saved_cursor = (self.cursor_row, self.cursor_col)
            self._saved_attrs = self._attrs.copy()
        elif cmd == "u":
            # Restore cursor position
            self.cursor_row, self.cursor_col = self._saved_cursor
            self._attrs = self._saved_attrs.copy()
        elif cmd == "h":
            self._handle_mode_set(params_str)
        elif cmd == "l":
            self._handle_mode_reset(params_str)
        elif cmd == "X":
            # Erase characters
            n = max(params[0], 1)
            for i in range(n):
                col = self.cursor_col + i
                if col < self.cols:
                    self._grid[self.cursor_row][col] = Cell(" ", self._attrs.copy())
            self._dirty_lines.add(self.cursor_row)

    def _handle_mode_set(self, params_str):
        """Handle CSI ? ... h (mode set).

        Args:
            params_str: Raw parameter string.
        """
        if "?1049" in params_str or "?47" in params_str:
            # Switch to alternate screen buffer
            if not self._using_alt:
                self._alt_grid = self._grid
                self._alt_cursor = (self.cursor_row, self.cursor_col)
                self._alt_scroll_region = (self._scroll_top, self._scroll_bottom)
                self._grid = [self._empty_line() for _ in range(self.rows)]
                self.cursor_row = 0
                self.cursor_col = 0
                self._scroll_top = 0
                self._scroll_bottom = self.rows - 1
                self._using_alt = True
                self._dirty_lines = set(range(self.rows))

    def _handle_mode_reset(self, params_str):
        """Handle CSI ? ... l (mode reset).

        Args:
            params_str: Raw parameter string.
        """
        if "?1049" in params_str or "?47" in params_str:
            # Switch back to main screen buffer
            if self._using_alt and self._alt_grid is not None:
                self._grid = self._alt_grid
                self.cursor_row, self.cursor_col = self._alt_cursor
                if hasattr(self, "_alt_scroll_region"):
                    self._scroll_top, self._scroll_bottom = self._alt_scroll_region
                else:
                    self._scroll_top = 0
                    self._scroll_bottom = self.rows - 1
                self._alt_grid = None
                self._alt_cursor = None
                self._using_alt = False
                self._dirty_lines = set(range(self.rows))

    def _handle_erase_display(self, mode):
        """Handle CSI J (erase in display).

        Args:
            mode: 0=below, 1=above, 2=all, 3=all+scrollback.
        """
        if mode == 0:
            # Erase from cursor to end of screen
            line = self._grid[self.cursor_row]
            for c in range(self.cursor_col, self.cols):
                line[c] = Cell(" ", CellAttrs())
            for r in range(self.cursor_row + 1, self.rows):
                self._grid[r] = self._empty_line()
        elif mode == 1:
            # Erase from start to cursor
            for r in range(self.cursor_row):
                self._grid[r] = self._empty_line()
            line = self._grid[self.cursor_row]
            for c in range(self.cursor_col + 1):
                line[c] = Cell(" ", CellAttrs())
        elif mode in (2, 3):
            # Erase entire screen
            for r in range(self.rows):
                self._grid[r] = self._empty_line()
            if mode == 3:
                self._scrollback.clear()
        self._dirty_lines = set(range(self.rows))

    def _handle_erase_line(self, mode):
        """Handle CSI K (erase in line).

        Args:
            mode: 0=to end, 1=to start, 2=entire line.
        """
        line = self._grid[self.cursor_row]
        if mode == 0:
            for c in range(self.cursor_col, self.cols):
                line[c] = Cell(" ", CellAttrs())
        elif mode == 1:
            for c in range(self.cursor_col + 1):
                line[c] = Cell(" ", CellAttrs())
        elif mode == 2:
            self._grid[self.cursor_row] = self._empty_line()
        self._dirty_lines.add(self.cursor_row)

    def _insert_lines(self, count):
        """Insert blank lines at cursor position.

        Args:
            count: Number of lines to insert.
        """
        for _ in range(count):
            if self.cursor_row <= self._scroll_bottom:
                self._grid.pop(self._scroll_bottom)
                self._grid.insert(self.cursor_row, self._empty_line())
        self._dirty_lines = set(range(self.rows))

    def _delete_lines(self, count):
        """Delete lines at cursor position.

        Args:
            count: Number of lines to delete.
        """
        for _ in range(count):
            if self.cursor_row <= self._scroll_bottom:
                self._grid.pop(self.cursor_row)
                self._grid.insert(self._scroll_bottom, self._empty_line())
        self._dirty_lines = set(range(self.rows))

    def _delete_chars(self, count):
        """Delete characters at cursor position, shifting left.

        Args:
            count: Number of characters to delete.
        """
        line = self._grid[self.cursor_row]
        col = self.cursor_col
        for _ in range(count):
            if col < self.cols:
                line.pop(col)
                line.append(Cell(" ", CellAttrs()))
        self._dirty_lines.add(self.cursor_row)

    def _insert_chars(self, count):
        """Insert blank characters at cursor position, shifting right.

        Args:
            count: Number of characters to insert.
        """
        line = self._grid[self.cursor_row]
        col = self.cursor_col
        for _ in range(count):
            line.insert(col, Cell(" ", CellAttrs()))
            if len(line) > self.cols:
                line.pop()
        self._dirty_lines.add(self.cursor_row)

    def _handle_sgr(self, params):
        """Handle SGR (Select Graphic Rendition) parameters.

        Args:
            params: List of integer parameters.
        """
        i = 0
        while i < len(params):
            p = params[i]
            if p == 0:
                self._attrs = CellAttrs()
            elif p == 1:
                self._attrs.bold = True
            elif p == 2:
                pass  # dim -- ignore
            elif p == 3:
                self._attrs.italic = True
            elif p == 4:
                self._attrs.underline = True
            elif p == 7:
                self._attrs.reverse = True
            elif p == 22:
                self._attrs.bold = False
            elif p == 23:
                self._attrs.italic = False
            elif p == 24:
                self._attrs.underline = False
            elif p == 27:
                self._attrs.reverse = False
            elif 30 <= p <= 37:
                self._attrs.fg = _PALETTE_256[p - 30]
            elif p == 38:
                if i + 1 < len(params) and params[i + 1] == 5:
                    if i + 2 < len(params) and 0 <= params[i + 2] <= 255:
                        self._attrs.fg = _PALETTE_256[params[i + 2]]
                    i += 2
                elif i + 1 < len(params) and params[i + 1] == 2:
                    if i + 4 < len(params):
                        r, g, b = params[i + 2], params[i + 3], params[i + 4]
                        self._attrs.fg = (
                            f"#{min(r, 255):02x}{min(g, 255):02x}{min(b, 255):02x}"
                        )
                    i += 4
            elif p == 39:
                self._attrs.fg = DEFAULT_FG
            elif 40 <= p <= 47:
                self._attrs.bg = _PALETTE_256[p - 40]
            elif p == 48:
                if i + 1 < len(params) and params[i + 1] == 5:
                    if i + 2 < len(params) and 0 <= params[i + 2] <= 255:
                        self._attrs.bg = _PALETTE_256[params[i + 2]]
                    i += 2
                elif i + 1 < len(params) and params[i + 1] == 2:
                    if i + 4 < len(params):
                        r, g, b = params[i + 2], params[i + 3], params[i + 4]
                        self._attrs.bg = (
                            f"#{min(r, 255):02x}{min(g, 255):02x}{min(b, 255):02x}"
                        )
                    i += 4
            elif p == 49:
                self._attrs.bg = DEFAULT_BG
            elif 90 <= p <= 97:
                self._attrs.fg = _PALETTE_256[p - 90 + 8]
            elif 100 <= p <= 107:
                self._attrs.bg = _PALETTE_256[p - 100 + 8]
            i += 1

    def get_lines(self):
        """Get the current screen content as a list of line data.

        Each line is a list of (text_run, CellAttrs) tuples where
        consecutive cells with the same attributes are merged.

        Returns:
            List of lines, each a list of (text, CellAttrs) runs.
        """
        lines = []
        for row in self._grid:
            runs = []
            current_text = []
            current_attrs = None

            for cell in row:
                if current_attrs is not None and cell.attrs == current_attrs:
                    current_text.append(cell.char)
                else:
                    if current_text:
                        runs.append(("".join(current_text), current_attrs))
                    current_text = [cell.char]
                    current_attrs = cell.attrs

            if current_text:
                runs.append(("".join(current_text), current_attrs))

            lines.append(runs)
        return lines

    def get_scrollback_lines(self):
        """Get scrollback buffer content.

        Returns:
            List of lines from the scrollback buffer, each a list of
            (text, CellAttrs) runs.
        """
        lines = []
        for row in self._scrollback:
            runs = []
            current_text = []
            current_attrs = None

            for cell in row:
                if current_attrs is not None and cell.attrs == current_attrs:
                    current_text.append(cell.char)
                else:
                    if current_text:
                        runs.append(("".join(current_text), current_attrs))
                    current_text = [cell.char]
                    current_attrs = cell.attrs

            if current_text:
                runs.append(("".join(current_text), current_attrs))
            lines.append(runs)
        return lines

    def get_dirty_lines(self):
        """Get the set of dirty (changed) line indices and clear the set.

        Returns:
            Set of line indices that changed since last call.
        """
        dirty = self._dirty_lines
        self._dirty_lines = set()
        return dirty

    def reset(self):
        """Reset the screen buffer to initial state."""
        self._grid = [self._empty_line() for _ in range(self.rows)]
        self.cursor_row = 0
        self.cursor_col = 0
        self._attrs = CellAttrs()
        self._scrollback.clear()
        self._scroll_top = 0
        self._scroll_bottom = self.rows - 1
        self._using_alt = False
        self._alt_grid = None
        self._alt_cursor = None
        self._dirty_lines = set(range(self.rows))
        self.changed = True
