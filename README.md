# QGIS Terminal

[![QGIS Plugin](https://img.shields.io/badge/QGIS-Plugin-green.svg)](https://plugins.qgis.org/plugins/qgis_terminal)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An integrated terminal plugin for QGIS, similar to VS Code's integrated terminal. Provides a dockable terminal panel with full shell access, ANSI color support, and cross-platform compatibility.

## Features

- **Integrated Terminal**: A dockable terminal panel that works like VS Code's terminal
- **True Interactive Shell**: Full pty-based shell with history, tab completion, and signal handling
- **ANSI Color Support**: Colored output for commands like `ls --color`, `git`, and more
- **Cross-Platform**: Works on Linux, macOS, and Windows
- **Multiple Shells**: Auto-detects available shells (bash, zsh, sh, PowerShell, cmd)
- **Configurable**: Font, color scheme, shell path, and scrollback buffer settings
- **QGIS Integration**: Defaults to the current QGIS project directory

## Project Structure

```
qgis-terminal-plugin/
├── qgis_terminal/
│   ├── __init__.py              # Plugin entry point
│   ├── qgis_terminal.py         # Main plugin class
│   ├── metadata.txt             # Plugin metadata for QGIS
│   ├── deps_manager.py          # Dependency management
│   ├── uv_manager.py            # uv package manager support
│   ├── LICENSE                  # Plugin license
│   ├── terminal/                # Terminal implementation
│   │   ├── __init__.py
│   │   ├── ansi_parser.py       # ANSI escape sequence parser
│   │   ├── shell_process.py     # Cross-platform shell process manager
│   │   ├── terminal_view.py     # Terminal display widget
│   │   ├── terminal_widget.py   # Container with toolbar
│   │   └── terminal_dock.py     # QDockWidget wrapper
│   ├── dialogs/
│   │   ├── __init__.py
│   │   ├── settings_dock.py     # Settings panel
│   │   └── update_checker.py    # Update checker dialog
│   └── icons/
│       ├── terminal.svg         # Terminal icon
│       ├── settings.svg         # Settings icon
│       └── about.svg            # About icon
├── package_plugin.py            # Python packaging script
├── package_plugin.sh            # Bash packaging script
├── install.py                   # Python installation script
├── install.sh                   # Bash installation script
├── README.md                    # This file
└── LICENSE                      # Repository license
```

## Requirements

- QGIS 3.28 or later (compatible with both QGIS 3.x on Qt5 and QGIS 4.0 on Qt6)
- Python 3.10+

## Installation

### Option A: QGIS Plugin Manager (Recommended)

1. Open QGIS
2. Go to **Plugins** -> **Manage and Install Plugins...**
3. Go to the **Settings** tab
4. Go to the **All** tab
5. Search for "QGIS Terminal"
6. Select the plugin and click **Install Plugin**

### Option B: Install Script

```bash
# Install
python install.py

# Or with bash
./install.sh

# Remove
python install.py --remove
```

### Option C: Manual Installation

Copy the `qgis_terminal` folder to your QGIS plugins directory:

- **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
- **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
- **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`

## Usage

1. Enable the plugin in QGIS: **Plugins** -> **Manage and Install Plugins...** -> Enable "QGIS Terminal"
2. Click the **Terminal** button in the toolbar, or go to **QGIS Terminal** -> **Terminal**
3. The terminal panel appears at the bottom of the QGIS window
4. Type commands and interact with the shell as you would in any terminal

### Keyboard Shortcuts

| Shortcut       | Action                                           |
| -------------- | ------------------------------------------------ |
| `Ctrl+C`       | Copy (if text selected) or send interrupt signal |
| `Ctrl+V`       | Paste from clipboard                             |
| `Ctrl+L`       | Clear screen                                     |
| `Ctrl+D`       | Send EOF                                         |
| `Ctrl+A`       | Select all                                       |
| `Up/Down`      | Navigate command history                         |
| `Tab`          | Shell tab completion                             |
| `Page Up/Down` | Scroll terminal output                           |

### Toolbar Actions

- **Shell Selector**: Choose between available shells (bash, zsh, PowerShell, etc.)
- **Clear**: Clear the terminal output
- **Restart**: Kill the current shell and start a new one

## How It Works

### Architecture

The terminal is built from four main components:

1. **AnsiParser** (`ansi_parser.py`): Parses ANSI/VT100 escape sequences and converts them to Qt text formatting (colors, bold, underline, etc.)

2. **ShellProcess** (`shell_process.py`): Cross-platform shell process manager
   - **Unix**: Uses `pty.openpty()` for true terminal emulation with `QSocketNotifier` for non-blocking I/O
   - **Windows**: Uses `subprocess.Popen` with pipe-based I/O and `QTimer` polling

3. **TerminalView** (`terminal_view.py`): A `QPlainTextEdit` subclass that displays terminal output and forwards keyboard input to the shell

4. **TerminalWidget** (`terminal_widget.py`): Container with toolbar and terminal view, manages the shell lifecycle

### Design Decisions

- **pty-based terminal** (not QProcess): Provides true terminal emulation where shell history, tab completion, and interactive programs work natively
- **Read-only QPlainTextEdit + key forwarding**: The pty handles echo and line editing; no complex input buffer tracking needed
- **No external dependencies**: Uses only Python stdlib and the `qgis.PyQt` abstraction (works on both Qt5 and Qt6)
- **QPlainTextEdit over QTextEdit**: Better performance for large output, supports scrollback limiting

## Packaging

```bash
# Package for QGIS plugin repository
python package_plugin.py

# Custom output path
python package_plugin.py --output /path/to/output.zip
```

## License

This project is released under the MIT License. See [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Links

- [GitHub Repository](https://github.com/opengeos/qgis-terminal-plugin)
- [Issue Tracker](https://github.com/opengeos/qgis-terminal-plugin/issues)
- [QGIS Plugin Development Documentation](https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/)
- [PyQGIS Developer Cookbook](https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/)
