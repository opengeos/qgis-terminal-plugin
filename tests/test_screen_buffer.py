"""Regression tests for terminal screen buffer escape handling."""

from qgis_terminal.terminal.screen_buffer import ScreenBuffer


def _screen_text(screen):
    """Return the rendered screen as plain text.

    Args:
        screen: ScreenBuffer instance to inspect.

    Returns:
        Plain text content with trailing cell padding removed from each line.
    """
    lines = []
    for line in screen.get_lines():
        lines.append("".join(text for text, _attrs in line).rstrip())
    return "\n".join(lines).rstrip()


def test_csi_with_space_intermediate_is_consumed():
    """Verify cursor-style CSI sequences do not leak visible bytes."""
    screen = ScreenBuffer(rows=3, cols=40)

    screen.feed("gpt-5.5 high ~ \x1b[0 q")

    text = _screen_text(screen)
    assert text == "gpt-5.5 high ~"
    assert "[0 q" not in text


def test_split_csi_with_space_intermediate_is_consumed():
    """Verify split cursor-style CSI sequences are buffered and consumed."""
    screen = ScreenBuffer(rows=3, cols=40)

    screen.feed("gpt-5.5 high ~ \x1b[0 ")
    screen.feed("q")

    text = _screen_text(screen)
    assert text == "gpt-5.5 high ~"
    assert "[0 q" not in text


def test_csi_tilde_sequence_is_consumed():
    """Verify CSI final bytes outside letters are consumed."""
    screen = ScreenBuffer(rows=3, cols=40)

    screen.feed("before\x1b[200~after")

    assert _screen_text(screen) == "beforeafter"


def test_hash_selector_escape_is_consumed():
    """Verify two-byte selector escapes do not leak their payload byte."""
    screen = ScreenBuffer(rows=3, cols=40)

    screen.feed("before\x1b#8after")

    assert _screen_text(screen) == "beforeafter"
