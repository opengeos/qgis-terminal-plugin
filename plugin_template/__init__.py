"""
QGIS Plugin Template

A template for creating QGIS plugins with dockable panels.
This plugin provides a starting point for developing custom QGIS plugins.
"""

from .deps_manager import ensure_venv_packages_available

# Add venv site-packages to sys.path so plugin dependencies are importable.
# This is a no-op if the venv has not been created yet.
ensure_venv_packages_available()

from .plugin_template import PluginTemplate


def classFactory(iface):
    """Load PluginTemplate class from file plugin_template.

    Args:
        iface: A QGIS interface instance.

    Returns:
        PluginTemplate: The plugin instance.
    """
    return PluginTemplate(iface)
