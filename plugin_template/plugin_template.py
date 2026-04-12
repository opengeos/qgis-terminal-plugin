"""
QGIS Plugin Template - Main Plugin Class

This module contains the main plugin class that manages the QGIS interface
integration, menu items, toolbar buttons, and dockable panels.
"""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMenu, QToolBar, QMessageBox


class PluginTemplate:
    """Plugin Template implementation class for QGIS."""

    def __init__(self, iface):
        """Constructor.

        Args:
            iface: An interface instance that provides the hook to QGIS.
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = None
        self.toolbar = None

        # Dock widgets (lazy loaded)
        self._sample_dock = None
        self._settings_dock = None

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        checkable=False,
        parent=None,
    ):
        """Add a toolbar icon to the toolbar.

        Args:
            icon_path: Path to the icon for this action.
            text: Text that appears in the menu for this action.
            callback: Function to be called when the action is triggered.
            enabled_flag: A flag indicating if the action should be enabled.
            add_to_menu: Flag indicating whether action should be added to menu.
            add_to_toolbar: Flag indicating whether action should be added to toolbar.
            status_tip: Optional text to show in status bar when mouse hovers over action.
            checkable: Whether the action is checkable (toggle).
            parent: Parent widget for the new action.

        Returns:
            The action that was created.
        """
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        action.setCheckable(checkable)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.menu.addAction(action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""
        # Create menu
        self.menu = QMenu("&Plugin Template")
        self.iface.mainWindow().menuBar().addMenu(self.menu)

        # Create toolbar
        self.toolbar = QToolBar("Plugin Template Toolbar")
        self.toolbar.setObjectName("PluginTemplateToolbar")
        self.iface.addToolBar(self.toolbar)

        # Get icon paths
        icon_base = os.path.join(self.plugin_dir, "icons")

        # Main panel icon - use custom icon or fallback to QGIS default
        main_icon = os.path.join(icon_base, "icon.png")
        if not os.path.exists(main_icon):
            main_icon = ":/images/themes/default/mActionAddRasterLayer.svg"

        settings_icon = os.path.join(icon_base, "settings.svg")
        if not os.path.exists(settings_icon):
            settings_icon = ":/images/themes/default/mActionOptions.svg"

        about_icon = os.path.join(icon_base, "about.svg")
        if not os.path.exists(about_icon):
            about_icon = ":/images/themes/default/mActionHelpContents.svg"

        # Add Sample Panel action (checkable for dock toggle)
        self.sample_action = self.add_action(
            main_icon,
            "Sample Panel",
            self.toggle_sample_dock,
            status_tip="Toggle Sample Panel",
            checkable=True,
            parent=self.iface.mainWindow(),
        )

        # Add Settings Panel action (checkable for dock toggle)
        self.settings_action = self.add_action(
            settings_icon,
            "Settings Panel",
            self.toggle_settings_dock,
            status_tip="Toggle Settings Panel",
            checkable=True,
            parent=self.iface.mainWindow(),
        )

        # Add separator to menu
        self.menu.addSeparator()

        # Update icon - use QGIS default download/update icon
        update_icon = ":/images/themes/default/mActionRefresh.svg"

        # Add Check for Updates action (menu only)
        self.add_action(
            update_icon,
            "Check for Updates...",
            self.show_update_checker,
            add_to_toolbar=False,
            status_tip="Check for plugin updates from GitHub",
            parent=self.iface.mainWindow(),
        )

        # Add About action (menu only)
        self.add_action(
            about_icon,
            "About Plugin Template",
            self.show_about,
            add_to_toolbar=False,
            status_tip="About Plugin Template",
            parent=self.iface.mainWindow(),
        )

    def unload(self):
        """Remove the plugin menu item and icon from QGIS GUI."""
        # Remove dock widgets
        if self._sample_dock:
            self.iface.removeDockWidget(self._sample_dock)
            self._sample_dock.deleteLater()
            self._sample_dock = None

        if self._settings_dock:
            self.iface.removeDockWidget(self._settings_dock)
            self._settings_dock.deleteLater()
            self._settings_dock = None

        # Remove actions from menu
        for action in self.actions:
            self.iface.removePluginMenu("&Plugin Template", action)

        # Remove toolbar
        if self.toolbar:
            del self.toolbar

        # Remove menu
        if self.menu:
            self.menu.deleteLater()

    def toggle_sample_dock(self):
        """Toggle the Sample dock widget visibility."""
        if self._sample_dock is None:
            try:
                from .dialogs.sample_dock import SampleDockWidget

                self._sample_dock = SampleDockWidget(
                    self.iface, self.iface.mainWindow()
                )
                self._sample_dock.setObjectName("PluginTemplateSampleDock")
                self._sample_dock.visibilityChanged.connect(
                    self._on_sample_visibility_changed
                )
                self.iface.addDockWidget(Qt.RightDockWidgetArea, self._sample_dock)
                self._sample_dock.show()
                self._sample_dock.raise_()
                return

            except Exception as e:
                QMessageBox.critical(
                    self.iface.mainWindow(),
                    "Error",
                    f"Failed to create Sample panel:\n{str(e)}",
                )
                self.sample_action.setChecked(False)
                return

        # Toggle visibility
        if self._sample_dock.isVisible():
            self._sample_dock.hide()
        else:
            self._sample_dock.show()
            self._sample_dock.raise_()

    def _on_sample_visibility_changed(self, visible):
        """Handle Sample dock visibility change."""
        self.sample_action.setChecked(visible)

    def toggle_settings_dock(self):
        """Toggle the Settings dock widget visibility."""
        if self._settings_dock is None:
            try:
                from .dialogs.settings_dock import SettingsDockWidget

                self._settings_dock = SettingsDockWidget(
                    self.iface, self.iface.mainWindow()
                )
                self._settings_dock.setObjectName("PluginTemplateSettingsDock")
                self._settings_dock.visibilityChanged.connect(
                    self._on_settings_visibility_changed
                )
                self.iface.addDockWidget(Qt.RightDockWidgetArea, self._settings_dock)
                self._settings_dock.show()
                self._settings_dock.raise_()
                return

            except Exception as e:
                QMessageBox.critical(
                    self.iface.mainWindow(),
                    "Error",
                    f"Failed to create Settings panel:\n{str(e)}",
                )
                self.settings_action.setChecked(False)
                return

        # Toggle visibility
        if self._settings_dock.isVisible():
            self._settings_dock.hide()
        else:
            self._settings_dock.show()
            self._settings_dock.raise_()

    def _on_settings_visibility_changed(self, visible):
        """Handle Settings dock visibility change."""
        self.settings_action.setChecked(visible)

    def show_about(self):
        """Display the about dialog."""
        # Read version from metadata.txt
        version = "Unknown"
        try:
            metadata_path = os.path.join(self.plugin_dir, "metadata.txt")
            with open(metadata_path, "r", encoding="utf-8") as f:
                import re

                content = f.read()
                version_match = re.search(r"^version=(.+)$", content, re.MULTILINE)
                if version_match:
                    version = version_match.group(1).strip()
        except Exception as e:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Plugin Template",
                f"Could not read version from metadata.txt:\n{str(e)}",
            )

        about_text = f"""
<h2>Plugin Template for QGIS</h2>
<p>Version: {version}</p>
<p>Author: Your Name</p>

<h3>Features:</h3>
<ul>
<li><b>Dockable Panels:</b> Sample panels that can be docked anywhere in the QGIS interface</li>
<li><b>Update Checker:</b> Check for plugin updates from GitHub</li>
<li><b>Settings Panel:</b> Configure plugin options</li>
</ul>

<h3>Links:</h3>
<ul>
<li><a href="https://github.com/opengeos/qgis-plugin-template">GitHub Repository</a></li>
<li><a href="https://github.com/opengeos/qgis-plugin-template/issues">Report Issues</a></li>
</ul>

<p>Licensed under MIT License</p>
"""
        QMessageBox.about(
            self.iface.mainWindow(),
            "About Plugin Template",
            about_text,
        )

    def show_update_checker(self):
        """Display the update checker dialog."""
        try:
            from .dialogs.update_checker import UpdateCheckerDialog
        except ImportError as e:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error",
                f"Failed to import update checker dialog:\n{str(e)}",
            )
            return

        try:
            dialog = UpdateCheckerDialog(self.plugin_dir, self.iface.mainWindow())
            dialog.exec_()
        except Exception as e:
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Error",
                f"Failed to open update checker:\n{str(e)}",
            )
