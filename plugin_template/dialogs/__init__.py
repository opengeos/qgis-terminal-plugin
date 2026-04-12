"""
Plugin Template Dialogs

This module contains the dialog and dock widget classes for the plugin template.
"""

from .sample_dock import SampleDockWidget
from .settings_dock import SettingsDockWidget
from .update_checker import UpdateCheckerDialog

__all__ = [
    "SampleDockWidget",
    "SettingsDockWidget",
    "UpdateCheckerDialog",
]
