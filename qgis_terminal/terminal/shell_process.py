"""
Cross-Platform Shell Process Manager

Manages the shell subprocess with platform-specific implementations:
- Unix (Linux/macOS): Uses pty for true terminal emulation
- Windows: Uses pywinpty (ConPTY) for true terminal emulation
"""

import os
import sys
import signal
import platform
import threading

from qgis.PyQt.QtCore import Qt, QObject, QTimer, pyqtSignal


def get_default_shell():
    """Get the default shell for the current platform.

    Returns:
        Path to the default shell executable.
    """
    if sys.platform == "win32":
        # Prefer PowerShell, fall back to cmd
        pwsh = os.path.join(
            os.environ.get("SystemRoot", r"C:\Windows"),
            "System32",
            "WindowsPowerShell",
            "v1.0",
            "powershell.exe",
        )
        if os.path.exists(pwsh):
            return pwsh
        return os.environ.get("COMSPEC", "cmd.exe")
    else:
        return os.environ.get("SHELL", "/bin/bash")


def get_available_shells():
    """Get a list of available shell executables.

    Returns:
        List of (display_name, path) tuples.
    """
    shells = []
    if sys.platform == "win32":
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        shells.append(("cmd", comspec))
        pwsh = os.path.join(
            os.environ.get("SystemRoot", r"C:\Windows"),
            "System32",
            "WindowsPowerShell",
            "v1.0",
            "powershell.exe",
        )
        if os.path.exists(pwsh):
            shells.append(("PowerShell", pwsh))
        # Check for pwsh (PowerShell Core)
        for p in os.environ.get("PATH", "").split(os.pathsep):
            pwsh_core = os.path.join(p, "pwsh.exe")
            if os.path.exists(pwsh_core):
                shells.append(("PowerShell Core", pwsh_core))
                break
    else:
        for name, path in [
            ("bash", "/bin/bash"),
            ("zsh", "/bin/zsh"),
            ("sh", "/bin/sh"),
            ("fish", "/usr/bin/fish"),
        ]:
            if os.path.exists(path):
                shells.append((name, path))
        # Also check user's SHELL
        user_shell = os.environ.get("SHELL", "")
        if user_shell and not any(path == user_shell for _, path in shells):
            name = os.path.basename(user_shell)
            shells.append((name, user_shell))
    return shells


class ShellProcess(QObject):
    """Base class for shell process management."""

    output_ready = pyqtSignal(str)
    process_exited = pyqtSignal(int)

    def start(self, shell_path, cwd=None, env=None):
        """Start the shell process.

        Args:
            shell_path: Path to the shell executable.
            cwd: Working directory for the shell.
            env: Environment variables dict.
        """
        raise NotImplementedError

    def write(self, data):
        """Write data to the shell's stdin.

        Args:
            data: Bytes to write.
        """
        raise NotImplementedError

    def resize(self, rows, cols):
        """Resize the terminal.

        Args:
            rows: Number of rows.
            cols: Number of columns.
        """
        pass

    def terminate(self):
        """Terminate the shell process."""
        raise NotImplementedError

    def is_running(self):
        """Check if the shell process is still running.

        Returns:
            True if the process is running.
        """
        raise NotImplementedError


class UnixShellProcess(ShellProcess):
    """Unix shell process using pty for true terminal emulation."""

    def __init__(self, parent=None):
        """Initialize the Unix shell process.

        Args:
            parent: Parent QObject.
        """
        super().__init__(parent)
        self._master_fd = None
        self._child_pid = None
        self._notifier = None

    def start(self, shell_path, cwd=None, env=None):
        """Start the shell using a pseudo-terminal.

        Args:
            shell_path: Path to the shell executable.
            cwd: Working directory.
            env: Environment variables.
        """
        import pty
        import fcntl

        if env is None:
            env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env["COLORTERM"] = "truecolor"

        if cwd is None:
            cwd = os.path.expanduser("~")

        master_fd, slave_fd = pty.openpty()
        pid = os.fork()

        if pid == 0:
            # Child process
            os.close(master_fd)
            os.setsid()

            # Set the slave as the controlling terminal
            import fcntl as child_fcntl
            import termios

            child_fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)

            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)
            if slave_fd > 2:
                os.close(slave_fd)

            os.chdir(cwd)
            # Replace the forked child with the user's shell. shell_path is
            # resolved from settings or the platform default, never from
            # terminal keystrokes; running a shell is the plugin's feature.
            os.execvpe(shell_path, [shell_path], env)  # nosec B606
        else:
            # Parent process
            os.close(slave_fd)
            self._master_fd = master_fd
            self._child_pid = pid

            # Set non-blocking
            flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
            fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            # Use QSocketNotifier for efficient I/O
            from qgis.PyQt.QtCore import QSocketNotifier

            self._notifier = QSocketNotifier(master_fd, QSocketNotifier.Type.Read, self)
            self._notifier.activated.connect(self._on_data_ready)

    def _on_data_ready(self):
        """Handle data available on the master fd."""
        try:
            data = os.read(self._master_fd, 65536)
            if data:
                text = data.decode("utf-8", errors="replace")
                self.output_ready.emit(text)
            else:
                self._handle_exit()
        except OSError:
            self._handle_exit()

    def _handle_exit(self):
        """Handle child process exit."""
        if self._notifier:
            self._notifier.setEnabled(False)
        exit_code = 0
        if self._child_pid:
            try:
                _, status = os.waitpid(self._child_pid, os.WNOHANG)
                if os.WIFEXITED(status):
                    exit_code = os.WEXITSTATUS(status)
            except ChildProcessError:
                pass
            self._child_pid = None
        self.process_exited.emit(exit_code)

    def write(self, data):
        """Write data to the shell.

        Args:
            data: Bytes to send to the shell.
        """
        if self._master_fd is not None:
            try:
                os.write(self._master_fd, data)
            except OSError:
                pass

    def resize(self, rows, cols):
        """Resize the pseudo-terminal.

        Args:
            rows: Number of rows.
            cols: Number of columns.
        """
        if self._master_fd is not None:
            import struct
            import fcntl
            import termios

            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            try:
                fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, winsize)
                if self._child_pid:
                    os.kill(self._child_pid, signal.SIGWINCH)
            except (OSError, ProcessLookupError):
                pass

    def terminate(self):
        """Terminate the shell process."""
        if self._notifier:
            self._notifier.setEnabled(False)
            self._notifier = None

        if self._child_pid:
            try:
                os.kill(self._child_pid, signal.SIGTERM)
                # Give it a moment then force kill
                QTimer.singleShot(500, self._force_kill)
            except ProcessLookupError:
                self._child_pid = None

        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = None

    def _force_kill(self):
        """Force kill the child process if still running."""
        if self._child_pid:
            try:
                os.kill(self._child_pid, signal.SIGKILL)
                os.waitpid(self._child_pid, os.WNOHANG)
            except (ProcessLookupError, ChildProcessError):
                pass
            self._child_pid = None

    def is_running(self):
        """Check if the shell process is running.

        Returns:
            True if the process is running.
        """
        if self._child_pid is None:
            return False
        try:
            pid, _ = os.waitpid(self._child_pid, os.WNOHANG)
            return pid == 0
        except ChildProcessError:
            self._child_pid = None
            return False


class WindowsShellProcess(ShellProcess):
    """Windows shell process using pywinpty (ConPTY pseudo-console).

    Wraps the Windows pseudo-console API so PowerShell's PSReadLine,
    ``cmd.exe`` line editing, and PTY-aware CLIs (``gemini``, ``claude``,
    ``ipython``, ...) all see a real terminal on stdin. The previous
    pipe-based backend looked like a non-interactive batch session to those
    programs, which broke backspace/delete in PowerShell, made ``cmd.exe``
    swallow keystrokes, and caused ``isatty()`` checks to fail.

    ``pywinpty.PtyProcess.read()`` is blocking and Windows handles can't be
    watched with ``QSocketNotifier``, so output is drained on a daemon
    reader thread and forwarded to the GUI thread via queued signals.
    """

    _data_ready = pyqtSignal(str)
    _exit_ready = pyqtSignal(int)

    def __init__(self, parent=None):
        """Initialize the Windows shell process.

        Args:
            parent: Parent QObject.
        """
        super().__init__(parent)
        self._proc = None
        self._reader = None
        self._stop = threading.Event()
        self._data_ready.connect(self.output_ready, Qt.ConnectionType.QueuedConnection)
        self._exit_ready.connect(
            self.process_exited, Qt.ConnectionType.QueuedConnection
        )

    def start(self, shell_path, cwd=None, env=None):
        """Start the shell inside a ConPTY pseudo-console.

        Args:
            shell_path: Path to the shell executable.
            cwd: Working directory.
            env: Environment variables.
        """
        import winpty  # pywinpty; import name differs from pip name.

        if env is None:
            env = os.environ.copy()
        env.setdefault("TERM", "xterm-256color")

        if cwd is None:
            cwd = os.path.expanduser("~")

        self._stop.clear()
        self._proc = winpty.PtyProcess.spawn(
            [shell_path],
            cwd=cwd,
            env=env,
            dimensions=(24, 80),
        )
        self._reader = threading.Thread(
            target=self._reader_loop, name="qgis-terminal-pty-reader", daemon=True
        )
        self._reader.start()

    def _reader_loop(self):
        """Drain pywinpty output on a background thread.

        pywinpty's ``read`` blocks until data is available or the child
        exits. Decode here so the GUI thread only sees text. Use a queued
        connection on ``_data_ready`` so emission marshals back onto the
        Qt event loop.
        """
        exit_code = 0
        try:
            while not self._stop.is_set():
                try:
                    data = self._proc.read(4096)
                except EOFError:
                    break
                if not data:
                    break
                if isinstance(data, bytes):
                    text = data.decode("utf-8", errors="replace")
                else:
                    text = data
                self._data_ready.emit(text)
        finally:
            try:
                exit_code = int(getattr(self._proc, "exitstatus", 0) or 0)
            except (TypeError, ValueError):
                exit_code = 0
            self._exit_ready.emit(exit_code)

    def write(self, data):
        """Write data to the shell's stdin.

        Args:
            data: Bytes (or str) to send to the shell.
        """
        if not self._proc or not self._proc.isalive():
            return
        if isinstance(data, bytes):
            # pywinpty's PtyProcess opens in text mode by default and rejects
            # bytes; the rest of the plugin produces utf-8 bytes (terminal_view
            # encodes keystrokes that way), so decode at the boundary.
            data = data.decode("utf-8", errors="replace")
        try:
            self._proc.write(data)
        except (OSError, EOFError):
            pass

    def resize(self, rows, cols):
        """Resize the pseudo-console.

        Args:
            rows: Number of rows.
            cols: Number of columns.
        """
        if not self._proc or not self._proc.isalive():
            return
        try:
            self._proc.setwinsize(rows, cols)
        except OSError:
            pass

    def terminate(self):
        """Terminate the shell process and join the reader thread."""
        self._stop.set()
        if self._proc is not None:
            try:
                self._proc.terminate(force=True)
            except (OSError, EOFError):
                pass
        if self._reader is not None:
            self._reader.join(timeout=1.0)
        self._proc = None
        self._reader = None

    def is_running(self):
        """Check if the shell process is running.

        Returns:
            True if the process is running.
        """
        return self._proc is not None and self._proc.isalive()


def create_shell_process(parent=None):
    """Create a platform-appropriate shell process.

    Args:
        parent: Parent QObject.

    Returns:
        A ShellProcess instance.
    """
    if sys.platform == "win32":
        return WindowsShellProcess(parent)
    else:
        return UnixShellProcess(parent)
