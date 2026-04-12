"""
QGIS Terminal Dialogs

This module contains the dialog and dock widget classes for the plugin.
"""

from .settings_dock import SettingsDockWidget
from .update_checker import UpdateCheckerDialog

__all__ = [
    "SettingsDockWidget",
    "UpdateCheckerDialog",
]
