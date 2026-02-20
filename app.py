import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QMessageBox, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt
from src.core.scanner import HardwareScanner
from src.core.loginctl_api import get_current_assignments
from src.ui.wizard import ExpressSetupWizard
from src.ui.advanced_ui import AdvancedSetupWindow

class MultiseatLauncher(QMainWindow):
    def __init__(self, hardware_data, live_mapping=None):
        super().__init__()
        self.hardware_data = hardware_data
        self.live_mapping = live_mapping or {}
        self.setWindowTitle("Multiseat Manager - Launcher")
        self.setMinimumSize(450, 300)
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Title
        title_label = QLabel("Welcome to Multiseat Manager")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Hardware Summary
        gpus = len(self.hardware_data.get("graphics", []))
        monitors = sum(len(gpu.get("monitors", [])) for gpu in self.hardware_data.get("graphics", []))
        inputs = len(self.hardware_data.get("inputs", []))
        # Exclude root hubs from usb count to just count external devices roughly
        usbs = sum(1 for v in self.hardware_data.get("usb", {}).values() if not v.get("is_hub", False))

        summary_text = (
            f"Detected Hardware:\n"
            f"• {gpus} GPUs\n"
            f"• {monitors} Displays\n"
            f"• {inputs} Input Devices\n"
        )
        summary_label = QLabel(summary_text)
        summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        summary_label.setStyleSheet("font-size: 14px; margin: 15px;")
        layout.addWidget(summary_label)

        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_express = QPushButton("Start Express Setup")
        self.btn_express.setMinimumHeight(50)
        self.btn_express.setStyleSheet("font-size: 14px; font-weight: bold; background-color: #2b579a; color: white;")
        self.btn_express.clicked.connect(self.start_express)

        self.btn_advanced = QPushButton("Advanced Manual Setup")
        self.btn_advanced.setMinimumHeight(50)
        self.btn_advanced.setStyleSheet("font-size: 14px;")
        self.btn_advanced.clicked.connect(self.start_advanced)

        btn_layout.addWidget(self.btn_express)
        btn_layout.addWidget(self.btn_advanced)
        
        layout.addLayout(btn_layout)

    def start_express(self):
        self.wizard = ExpressSetupWizard(self.hardware_data)
        self.wizard.accepted.connect(self.on_wizard_finished)
        self.wizard.rejected.connect(self.show)
        self.wizard.show()
        self.hide()

    def on_wizard_finished(self):
        mapping = self.wizard.get_mapping()
        self.start_advanced(initial_mapping=mapping)

    def start_advanced(self, checked=False, initial_mapping=None):
        # btn_advanced.clicked passes 'checked' as a bool. 
        # initial_mapping comes via python kwargs from on_wizard_finished.
        mapping = initial_mapping if initial_mapping is not None else self.live_mapping
        
        self.advanced_win = AdvancedSetupWindow(
            self.hardware_data, 
            on_wizard_request=self.show_wizard_from_advanced, 
            initial_mapping=mapping
        )
        self.advanced_win.show()
        if hasattr(self, 'wizard'):
            self.wizard.close()
        self.close()

    def show_wizard_from_advanced(self):
        if hasattr(self, 'advanced_win'):
            self.advanced_win.close()
        self.start_express()

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # Load Hardware
    scanner = HardwareScanner()
    try:
        hardware_data = scanner.full_scan()
        assignments = get_current_assignments()
        
        # Transform flat syspath map to group map
        live_mapping = {}
        for syspath, seat in assignments.items():
            if seat not in live_mapping:
                live_mapping[seat] = []
            live_mapping[seat].append(syspath)
            
    except Exception as e:
        QMessageBox.critical(None, "Hardware Scan Error", f"Failed to scan hardware:\n{str(e)}")
        sys.exit(1)

    launcher = MultiseatLauncher(hardware_data, live_mapping=live_mapping)
    launcher.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
