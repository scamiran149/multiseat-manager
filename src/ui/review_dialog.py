import os
import subprocess
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, 
    QTabWidget, QTextEdit, QMessageBox
)
from PyQt6.QtGui import QFont

class ReviewDialog(QDialog):
    def __init__(self, staging_dir, parent=None):
        super().__init__(parent)
        self.staging_dir = staging_dir
        self.setWindowTitle("Review Configuration Changes")
        self.resize(800, 600)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Load files from staging_dir
        for filename in sorted(os.listdir(self.staging_dir)):
            filepath = os.path.join(self.staging_dir, filename)
            if os.path.isfile(filepath):
                try:
                    with open(filepath, "r") as f:
                        content = f.read()
                    
                    text_edit = QTextEdit()
                    text_edit.setReadOnly(True)
                    text_edit.setPlainText(content)
                    text_edit.setFont(QFont("Monospace", 10))
                    self.tabs.addTab(text_edit, filename)
                except Exception:
                    pass

        btn_layout = QHBoxLayout()

        btn_open_folder = QPushButton("Open Staging Folder")
        btn_open_folder.clicked.connect(self.open_folder)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        btn_install = QPushButton("Install Now (sudo)")
        btn_install.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold; padding: 5px 15px;")
        btn_install.clicked.connect(self.install_now)

        btn_layout.addWidget(btn_open_folder)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_install)

        layout.addLayout(btn_layout)

    def open_folder(self):
        try:
            subprocess.Popen(["xdg-open", self.staging_dir])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not launch file manager:\n{str(e)}")

    def install_now(self):
        script_path = os.path.join(self.staging_dir, "apply_config.sh")
        if not os.path.exists(script_path):
            QMessageBox.critical(self, "Error", "apply_config.sh not found in staging directory!")
            return

        try:
            result = subprocess.run(
                ["pkexec", "bash", script_path],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                QMessageBox.information(self, "Success", "Configuration applied successfully!")
                self.accept()
            elif result.returncode in (126, 127):
                QMessageBox.warning(self, "Permission Denied", "Authentication was cancelled or failed. Configuration was not applied.")
            else:
                QMessageBox.critical(self, "Execution Failed", f"Failed to apply configuration (Code {result.returncode}):\n{result.stderr}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred:\n{str(e)}")
