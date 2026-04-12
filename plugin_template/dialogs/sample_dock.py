"""
Sample Dock Widget for Plugin Template

This module provides a sample dockable panel that demonstrates
how to create dock widgets for QGIS plugins.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QGroupBox,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QFormLayout,
    QMessageBox,
    QFileDialog,
    QProgressBar,
)
from qgis.PyQt.QtGui import QFont
from qgis.core import QgsProject, QgsMapLayerProxyModel


class SampleDockWidget(QDockWidget):
    """A sample dockable panel for demonstrating plugin functionality."""

    def __init__(self, iface, parent=None):
        """Initialize the dock widget.

        Args:
            iface: QGIS interface instance.
            parent: Parent widget.
        """
        super().__init__("Sample Panel", parent)
        self.iface = iface

        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the dock widget UI."""
        # Main widget
        main_widget = QWidget()
        self.setWidget(main_widget)

        # Main layout
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(10)

        # Header
        header_label = QLabel("Sample Panel")
        header_font = QFont()
        header_font.setPointSize(12)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)

        # Description
        desc_label = QLabel(
            "This is a sample dockable panel. Customize it for your plugin needs."
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: gray;")
        layout.addWidget(desc_label)

        # Input section
        input_group = QGroupBox("Input")
        input_layout = QFormLayout(input_group)

        # Layer selection
        self.layer_combo = QComboBox()
        self._populate_layers()
        input_layout.addRow("Layer:", self.layer_combo)

        # Text input
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("Enter some text...")
        input_layout.addRow("Text:", self.text_input)

        # Number input
        self.number_spin = QSpinBox()
        self.number_spin.setRange(0, 1000)
        self.number_spin.setValue(100)
        input_layout.addRow("Number:", self.number_spin)

        # Checkbox
        self.option_check = QCheckBox("Enable option")
        self.option_check.setChecked(True)
        input_layout.addRow("Option:", self.option_check)

        # File selection
        file_layout = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Select a file...")
        self.file_input.setReadOnly(True)
        file_layout.addWidget(self.file_input)
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_file)
        file_layout.addWidget(self.browse_btn)
        input_layout.addRow("File:", file_layout)

        layout.addWidget(input_group)

        # Output section
        output_group = QGroupBox("Output")
        output_layout = QVBoxLayout(output_group)

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMaximumHeight(150)
        self.output_text.setPlaceholderText("Results will appear here...")
        output_layout.addWidget(self.output_text)

        layout.addWidget(output_group)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Buttons
        button_layout = QHBoxLayout()

        self.run_btn = QPushButton("Run")
        self.run_btn.clicked.connect(self._run_action)
        button_layout.addWidget(self.run_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self._clear_output)
        button_layout.addWidget(self.clear_btn)

        layout.addLayout(button_layout)

        # Stretch at the end
        layout.addStretch()

        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self.status_label)

        # Connect to layer changes
        QgsProject.instance().layersAdded.connect(self._populate_layers)
        QgsProject.instance().layersRemoved.connect(self._populate_layers)

    def _populate_layers(self, *args):
        """Populate the layer combo box with available layers."""
        self.layer_combo.clear()
        self.layer_combo.addItem("-- Select a layer --", None)

        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            self.layer_combo.addItem(layer.name(), layer.id())

    def _browse_file(self):
        """Open file browser dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select File",
            "",
            "All Files (*);;GeoTIFF (*.tif *.tiff);;Shapefile (*.shp)",
        )
        if file_path:
            self.file_input.setText(file_path)

    def _run_action(self):
        """Execute the sample action."""
        # Get current values
        layer_id = self.layer_combo.currentData()
        text = self.text_input.text()
        number = self.number_spin.value()
        option = self.option_check.isChecked()
        file_path = self.file_input.text()

        # Show progress
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Processing...")
        self.status_label.setStyleSheet("color: blue; font-size: 10px;")

        # Simulate processing
        self.progress_bar.setValue(50)

        # Build output
        output_lines = [
            "=== Sample Action Results ===",
            "",
            f"Selected Layer ID: {layer_id or 'None'}",
            f"Text Input: {text or '(empty)'}",
            f"Number Value: {number}",
            f"Option Enabled: {option}",
            f"File Path: {file_path or '(none)'}",
            "",
            "Action completed successfully!",
        ]

        self.output_text.setPlainText("\n".join(output_lines))

        # Complete
        self.progress_bar.setValue(100)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Completed")
        self.status_label.setStyleSheet("color: green; font-size: 10px;")

        self.iface.messageBar().pushSuccess(
            "Plugin Template", "Sample action completed successfully!"
        )

    def _clear_output(self):
        """Clear the output text area."""
        self.output_text.clear()
        self.status_label.setText("Ready")
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")

    def closeEvent(self, event):
        """Handle dock widget close event."""
        # Disconnect signals
        try:
            QgsProject.instance().layersAdded.disconnect(self._populate_layers)
            QgsProject.instance().layersRemoved.disconnect(self._populate_layers)
        except (RuntimeError, TypeError):
            pass

        event.accept()
