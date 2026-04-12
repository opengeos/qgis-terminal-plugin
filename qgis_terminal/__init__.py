"""
QGIS Terminal

An integrated terminal plugin for QGIS, similar to VS Code's terminal.
Provides a dockable terminal panel with full shell access.
"""

from .deps_manager import ensure_venv_packages_available

# Add venv site-packages to sys.path so plugin dependencies are importable.
# This is a no-op if the venv has not been created yet.
ensure_venv_packages_available()

from .qgis_terminal import QgisTerminal


def classFactory(iface):
    """Load QgisTerminal class from file qgis_terminal.

    Args:
        iface: A QGIS interface instance.

    Returns:
        QgisTerminal: The plugin instance.
    """
    return QgisTerminal(iface)
