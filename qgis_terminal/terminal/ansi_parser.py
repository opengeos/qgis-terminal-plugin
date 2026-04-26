"""
ANSI Escape Sequence Parser

Parses VT100/ANSI escape sequences and produces styled text segments
for rendering in a QPlainTextEdit widget.
"""

import re
from dataclasses import dataclass, field

from qgis.PyQt.QtGui import QColor, QTextCharFormat, QFont

# VS Code-inspired dark theme color palette
DARK_PALETTE = [
    QColor("#1e1e1e"),  # 0: black
    QColor("#f44747"),  # 1: red
    QColor("#6a9955"),  # 2: green
    QColor("#dcdcaa"),  # 3: yellow
    QColor("#569cd6"),  # 4: blue
    QColor("#c586c0"),  # 5: magenta
    QColor("#4ec9b0"),  # 6: cyan
    QColor("#d4d4d4"),  # 7: white
    QColor("#808080"),  # 8: bright black (gray)
    QColor("#f44747"),  # 9: bright red
    QColor("#6a9955"),  # 10: bright green
    QColor("#dcdcaa"),  # 11: bright yellow
    QColor("#9cdcfe"),  # 12: bright blue
    QColor("#c586c0"),  # 13: bright magenta
    QColor("#4ec9b0"),  # 14: bright cyan
    QColor("#ffffff"),  # 15: bright white
]

# Default foreground and background
DEFAULT_FG = QColor("#d4d4d4")
DEFAULT_BG = QColor("#1e1e1e")

# 256-color lookup table (indices 16-231 are a 6x6x6 color cube,
# 232-255 are grayscale)
_COLOR_256 = None


def _build_256_color_table():
    """Build the xterm 256-color lookup table."""
    global _COLOR_256
    if _COLOR_256 is not None:
        return _COLOR_256

    table = list(DARK_PALETTE)  # 0-15: standard colors

    # 16-231: 6x6x6 color cube
    for r in range(6):
        for g in range(6):
            for b in range(6):
                rv = 55 + 40 * r if r else 0
                gv = 55 + 40 * g if g else 0
                bv = 55 + 40 * b if b else 0
                table.append(QColor(rv, gv, bv))

    # 232-255: grayscale ramp
    for i in range(24):
        v = 8 + 10 * i
        table.append(QColor(v, v, v))

    _COLOR_256 = table
    return _COLOR_256


@dataclass
class StyledSegment:
    """A segment of text with associated formatting."""

    text: str
    fmt: QTextCharFormat = field(default_factory=QTextCharFormat)


# Regex to match ANSI escape sequences
# Matches: ESC[ ... letter (CSI sequences) and ESC] ... BEL/ST (OSC sequences)
_CSI_RE = re.compile(r"\x1b\[([0-9;]*)([A-Za-z@`])")
_OSC_RE = re.compile(r"\x1b\].*?(?:\x07|\x1b\\)")
_ANY_ESCAPE_RE = re.compile(
    r"\x1b(?:\[([0-9;]*)([A-Za-z@`])|\].*?(?:\x07|\x1b\\)|[()][0-9A-Za-z]|[=>MNOP78])"
)


class AnsiParser:
    """Stateful ANSI escape sequence parser.

    Maintains the current text formatting state and parses incoming
    text into styled segments.
    """

    def __init__(self):
        """Initialize the parser with default formatting."""
        self._fg = QColor(DEFAULT_FG)
        self._bg = QColor(DEFAULT_BG)
        self._bold = False
        self._dim = False
        self._italic = False
        self._underline = False
        self._reverse = False

    def _make_format(self):
        """Create a QTextCharFormat from the current state.

        Returns:
            QTextCharFormat with current styling applied.
        """
        fmt = QTextCharFormat()
        fg = self._bg if self._reverse else self._fg
        bg = self._fg if self._reverse else self._bg
        fmt.setForeground(fg)
        fmt.setBackground(bg)
        if self._bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        if self._italic:
            fmt.setFontItalic(True)
        if self._underline:
            fmt.setFontUnderline(True)
        return fmt

    def _apply_sgr(self, params_str):
        """Apply SGR (Select Graphic Rendition) parameters.

        Args:
            params_str: Semicolon-separated SGR parameter string.
        """
        if not params_str:
            params = [0]
        else:
            try:
                params = [int(p) for p in params_str.split(";") if p]
            except ValueError:
                return

        table = _build_256_color_table()
        i = 0
        while i < len(params):
            p = params[i]
            if p == 0:
                # Reset
                self._fg = QColor(DEFAULT_FG)
                self._bg = QColor(DEFAULT_BG)
                self._bold = False
                self._dim = False
                self._italic = False
                self._underline = False
                self._reverse = False
            elif p == 1:
                self._bold = True
            elif p == 2:
                self._dim = True
            elif p == 3:
                self._italic = True
            elif p == 4:
                self._underline = True
            elif p == 7:
                self._reverse = True
            elif p == 22:
                self._bold = False
                self._dim = False
            elif p == 23:
                self._italic = False
            elif p == 24:
                self._underline = False
            elif p == 27:
                self._reverse = False
            elif 30 <= p <= 37:
                self._fg = QColor(table[p - 30])
            elif p == 38:
                # Extended foreground color
                if i + 1 < len(params) and params[i + 1] == 5:
                    # 256-color: ESC[38;5;Nm
                    if i + 2 < len(params) and 0 <= params[i + 2] <= 255:
                        self._fg = QColor(table[params[i + 2]])
                    i += 2
                elif i + 1 < len(params) and params[i + 1] == 2:
                    # 24-bit color: ESC[38;2;R;G;Bm
                    if i + 4 < len(params):
                        r, g, b = params[i + 2], params[i + 3], params[i + 4]
                        self._fg = QColor(min(r, 255), min(g, 255), min(b, 255))
                    i += 4
            elif p == 39:
                self._fg = QColor(DEFAULT_FG)
            elif 40 <= p <= 47:
                self._bg = QColor(table[p - 40])
            elif p == 48:
                # Extended background color
                if i + 1 < len(params) and params[i + 1] == 5:
                    # 256-color: ESC[48;5;Nm
                    if i + 2 < len(params) and 0 <= params[i + 2] <= 255:
                        self._bg = QColor(table[params[i + 2]])
                    i += 2
                elif i + 1 < len(params) and params[i + 1] == 2:
                    # 24-bit color: ESC[48;2;R;G;Bm
                    if i + 4 < len(params):
                        r, g, b = params[i + 2], params[i + 3], params[i + 4]
                        self._bg = QColor(min(r, 255), min(g, 255), min(b, 255))
                    i += 4
            elif p == 49:
                self._bg = QColor(DEFAULT_BG)
            elif 90 <= p <= 97:
                self._fg = QColor(table[p - 90 + 8])
            elif 100 <= p <= 107:
                self._bg = QColor(table[p - 100 + 8])
            i += 1

    def parse(self, data):
        """Parse a string containing ANSI escape sequences.

        Args:
            data: Raw string from the terminal, potentially containing
                ANSI escape sequences.

        Returns:
            A list of StyledSegment objects. Special segments may have
            text set to control strings like "\\x1b[2J" for clear screen
            or "\\x1b[K" for erase to end of line, which the caller
            should handle.
        """
        segments = []
        pos = 0
        text_buf = []

        while pos < len(data):
            ch = data[pos]

            if ch == "\x1b":
                # Flush accumulated text
                if text_buf:
                    segments.append(
                        StyledSegment("".join(text_buf), self._make_format())
                    )
                    text_buf = []

                # Try to match an escape sequence
                m = _ANY_ESCAPE_RE.match(data, pos)
                if m:
                    full = m.group(0)
                    # CSI sequence?
                    if m.group(1) is not None or m.group(2) is not None:
                        params_str = m.group(1) or ""
                        cmd = m.group(2)
                        if cmd == "m":
                            self._apply_sgr(params_str)
                        elif cmd == "K":
                            # Erase to end of line
                            segments.append(
                                StyledSegment("\x1b[K", self._make_format())
                            )
                        elif cmd == "J" and params_str in ("2", "3"):
                            # Clear screen
                            segments.append(
                                StyledSegment("\x1b[2J", self._make_format())
                            )
                        elif cmd == "H" and (not params_str or params_str == "1;1"):
                            # Cursor home
                            segments.append(
                                StyledSegment("\x1b[H", self._make_format())
                            )
                        # Other CSI sequences are silently stripped
                    # OSC and other sequences are silently stripped
                    pos = m.end()
                else:
                    # Unknown escape, skip ESC character
                    pos += 1
            elif ch == "\r":
                # Carriage return -- flush text, emit CR marker
                if text_buf:
                    segments.append(
                        StyledSegment("".join(text_buf), self._make_format())
                    )
                    text_buf = []
                segments.append(StyledSegment("\r", self._make_format()))
                pos += 1
            elif ch == "\x07":
                # Bell -- ignore
                pos += 1
            elif ch == "\x08":
                # Backspace
                if text_buf:
                    segments.append(
                        StyledSegment("".join(text_buf), self._make_format())
                    )
                    text_buf = []
                segments.append(StyledSegment("\x08", self._make_format()))
                pos += 1
            else:
                text_buf.append(ch)
                pos += 1

        # Flush remaining text
        if text_buf:
            segments.append(StyledSegment("".join(text_buf), self._make_format()))

        return segments

    def reset(self):
        """Reset the parser to default state."""
        self.__init__()
