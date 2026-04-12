# QGIS Plugin Template

A comprehensive template for creating QGIS plugins with dockable panels, update checker, and all the essential features needed for a professional plugin.

## Features

- **Dockable Panels**: Sample panels that can be docked anywhere in the QGIS interface
- **Plugin Update Checker**: Check for updates from GitHub and install them automatically
- **About Dialog**: Display version information and links
- **Settings Panel**: Configurable plugin options with persistent storage
- **Menu & Toolbar Integration**: Full integration with QGIS menu system and custom toolbar
- **Clean Code Structure**: Well-organized, documented, and following QGIS plugin best practices
- **Packaging Scripts**: Ready-to-use scripts for creating zip files for the official QGIS plugin repository

## Project Structure

```
qgis-plugin-template/
├── plugin_template/
│   ├── __init__.py              # Plugin entry point
│   ├── plugin_template.py       # Main plugin class
│   ├── metadata.txt             # Plugin metadata for QGIS
│   ├── LICENSE                  # Plugin license
│   ├── dialogs/
│   │   ├── __init__.py
│   │   ├── sample_dock.py       # Sample dockable panel
│   │   ├── settings_dock.py     # Settings panel
│   │   └── update_checker.py    # Update checker dialog
│   └── icons/
│       ├── icon.svg             # Main plugin icon
│       ├── settings.svg         # Settings icon
│       └── about.svg            # About icon
├── package_plugin.py                # Python packaging script
├── package_plugin.sh                # Bash packaging script
├── install.py                       # Python installation script
├── install.sh                       # Bash installation script
├── README.md                        # This file
└── LICENSE                          # Repository license
```

## Requirements

- QGIS 3.28 or later
- Python 3.10+

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/opengeos/qgis-plugin-template.git
cd qgis-plugin-template
```

### 2. Customize the Template

1. **Rename the plugin**:
   - Rename `plugin_template/` to your plugin name
   - Update class names in Python files (e.g., `PluginTemplate` → `YourPluginName`)
   - Update `metadata.txt` with your plugin information

2. **Update metadata.txt**:
   ```ini
   [general]
   name=Your Plugin Name
   version=0.1.0
   author=Your Name
   email=your.email@example.com
   description=Your plugin description
   repository=https://github.com/opengeos/your-plugin
   tracker=https://github.com/opengeos/your-plugin/issues
   ```

3. **Update GitHub URLs** in `plugin_template/dialogs/update_checker.py`:
   ```python
   GITHUB_REPO = "opengeos/your-plugin"
   GITHUB_BRANCH = "main"
   PLUGIN_PATH = "your_plugin"
   ```

### 3. Install for Development

Using Python:
```bash
python install.py
```

Using Bash:
```bash
./install.sh
```

### 4. Enable in QGIS

1. Restart QGIS
2. Go to `Plugins` → `Manage and Install Plugins...`
3. Find and enable your plugin

## Development

### Adding a New Dockable Panel

1. Create a new file in `dialogs/` (e.g., `my_dock.py`):

```python
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDockWidget, QWidget, QVBoxLayout, QLabel

class MyDockWidget(QDockWidget):
    def __init__(self, iface, parent=None):
        super().__init__("My Panel", parent)
        self.iface = iface
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        # Create widget content
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel("Hello from my panel!"))
        self.setWidget(widget)
```

2. Add the import to `dialogs/__init__.py`

3. Add toggle method in `plugin_template.py`:
```python
def toggle_my_dock(self):
    if self._my_dock is None:
        from .dialogs.my_dock import MyDockWidget
        self._my_dock = MyDockWidget(self.iface, self.iface.mainWindow())
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self._my_dock)

    if self._my_dock.isVisible():
        self._my_dock.hide()
    else:
        self._my_dock.show()
```

### Adding a Menu Action

```python
self.add_action(
    ":/images/themes/default/mActionOptions.svg",  # Icon path
    "My Action",                                     # Menu text
    self.my_action_callback,                        # Callback function
    status_tip="Description of action",
    add_to_toolbar=True,                            # Add to toolbar
    add_to_menu=True,                               # Add to menu
    parent=self.iface.mainWindow(),
)
```

### Storing Settings

Use `QSettings` for persistent configuration:

```python
from qgis.PyQt.QtCore import QSettings

settings = QSettings()

# Save setting
settings.setValue("PluginTemplate/my_setting", value)

# Load setting
value = settings.value("PluginTemplate/my_setting", default_value, type=str)
```

## Packaging for QGIS Plugin Repository

### Using Python Script

```bash
# Default packaging
python package_plugin.py

# Custom plugin name
python package_plugin.py --name my_plugin

# Custom output path
python package_plugin.py --output /path/to/my_plugin.zip

# Without version in filename
python package_plugin.py --no-version
```

### Using Bash Script

```bash
# Make executable (first time only)
chmod +x package_plugin.sh

# Default packaging
./package_plugin.sh

# Custom plugin name
./package_plugin.sh --name my_plugin

# Custom output directory
./package_plugin.sh --output /path/to/output
```

### Uploading to QGIS Plugin Repository

1. Create an account at [plugins.qgis.org](https://plugins.qgis.org/)
2. Go to "My plugins" and click "Add a new plugin"
3. Upload the generated zip file
4. Fill in the required information
5. Submit for review

## Installation Options

### Option A: QGIS Plugin Manager (Recommended)

1. Open QGIS
2. Go to **Plugins** → **Manage and Install Plugins...**
3. Go to the **Settings** tab
4. Click **Add...** under "Plugin Repositories"
5. Give a name for the repository, e.g., "OpenGeos"
6. Enter the URL of the repository: https://qgis.gishub.org/plugins.xml
7. Click **OK**
8. Go to the **All** tab
9. Search for your plugin name
10. Select your plugin from the list and click **Install Plugin**

### Option B: Install Script

```bash
# Install
python install.py

# Or with bash
./install.sh

# Remove
python install.py --remove

# Install with custom name
python install.py --name my_plugin
```

### Option C: Manual Installation

Copy the plugin folder to your QGIS plugins directory:

- **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
- **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
- **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`

## Plugin Update Checker

The template includes a built-in update checker that:

1. Fetches the latest version from your GitHub repository
2. Compares with the currently installed version
3. Downloads and installs updates automatically
4. Shows changelog information

To use it:
1. Go to `Plugin Template` → `Check for Updates...`
2. Click "Check for Updates"
3. If an update is available, click "Download and Install Update"
4. Restart QGIS to apply changes

## Customization Checklist

When using this template for your own plugin:

- [ ] Rename `plugin_template` folder to your plugin name
- [ ] Update `metadata.txt` with your information
- [ ] Update class names in all Python files
- [ ] Update menu names and toolbar names
- [ ] Update GitHub URLs in `update_checker.py`
- [ ] Replace icons with your own
- [ ] Update this README
- [ ] Update LICENSE if needed
- [ ] Add your plugin functionality

## Best Practices

1. **Lazy Loading**: Load heavy resources only when needed
2. **Error Handling**: Always wrap dock creation in try/except
3. **Cleanup**: Properly unload all resources in the `unload()` method
4. **Threading**: Use QThread for long-running operations
5. **Settings**: Use QSettings for persistent configuration
6. **Icons**: Use SVG icons for resolution independence
7. **Documentation**: Keep docstrings updated

## License

This template is released under the MIT License. See [LICENSE](LICENSE) for details.

When creating your own plugin, you may choose any license that suits your needs.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Links

- [QGIS Plugin Development Documentation](https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/)
- [PyQGIS Developer Cookbook](https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/)
- [QGIS Plugin Repository](https://plugins.qgis.org/)
- [Qt for Python Documentation](https://doc.qt.io/qtforpython/)