"""
Cross-Platform Shell Process Manager

Manages the shell subprocess with platform-specific implementations:
- Unix (Linux/macOS): Uses pty for true terminal emulation
- Windows: Uses subprocess with pipe-based I/O
"""

import os
import sys
import signal
import platform

from qgis.PyQt.QtCore import QObject, QTimer, pyqtSignal


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
            os.execvpe(shell_path, [shell_path], env)
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

            self._notifier = QSocketNotifier(master_fd, QSocketNotifier.Read, self)
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
    """Windows shell process using subprocess with pipe-based I/O."""

    def __init__(self, parent=None):
        """Initialize the Windows shell process.

        Args:
            parent: Parent QObject.
        """
        super().__init__(parent)
        self._process = None
        self._poll_timer = None

    def start(self, shell_path, cwd=None, env=None):
        """Start the shell using subprocess.

        Args:
            shell_path: Path to the shell executable.
            cwd: Working directory.
            env: Environment variables.
        """
        import subprocess

        if env is None:
            env = os.environ.copy()

        if cwd is None:
            cwd = os.path.expanduser("~")

        # Use CREATE_NEW_PROCESS_GROUP on Windows for Ctrl+C handling
        creation_flags = 0
        if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

        self._process = subprocess.Popen(
            [shell_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=env,
            creationflags=creation_flags,
            bufsize=0,
        )

        # Poll for output every 50ms
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_output)
        self._poll_timer.start(50)

    def _poll_output(self):
        """Poll stdout and stderr for available data."""
        if self._process is None:
            return

        if self._process.poll() is not None:
            # Process has exited, read remaining output
            self._read_remaining()
            self._poll_timer.stop()
            self.process_exited.emit(self._process.returncode)
            return

        self._read_available()

    def _read_available(self):
        """Read available data from stdout/stderr without blocking."""
        import msvcrt
        import ctypes

        for pipe in (self._process.stdout, self._process.stderr):
            if pipe is None:
                continue
            handle = msvcrt.get_osfhandle(pipe.fileno())
            avail = ctypes.c_ulong(0)
            ctypes.windll.kernel32.PeekNamedPipe(
                handle, None, 0, None, ctypes.byref(avail), None
            )
            if avail.value > 0:
                data = pipe.read(avail.value)
                if data:
                    text = data.decode("utf-8", errors="replace")
                    self.output_ready.emit(text)

    def _read_remaining(self):
        """Read any remaining output after process exit."""
        if self._process is None:
            return
        for pipe in (self._process.stdout, self._process.stderr):
            if pipe:
                data = pipe.read()
                if data:
                    text = data.decode("utf-8", errors="replace")
                    self.output_ready.emit(text)

    def write(self, data):
        """Write data to the shell's stdin.

        Args:
            data: Bytes to send to the shell.
        """
        if self._process and self._process.stdin:
            try:
                self._process.stdin.write(data)
                self._process.stdin.flush()
            except (BrokenPipeError, OSError):
                pass

    def terminate(self):
        """Terminate the shell process."""
        if self._poll_timer:
            self._poll_timer.stop()
            self._poll_timer = None

        if self._process:
            try:
                self._process.terminate()
            except OSError:
                pass
            self._process = None

    def is_running(self):
        """Check if the shell process is running.

        Returns:
            True if the process is running.
        """
        return self._process is not None and self._process.poll() is None


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
