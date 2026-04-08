from PyQt6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QLabel, QSpinBox, 
    QListWidget, QPushButton, QHBoxLayout, QListWidgetItem, QComboBox
)
from PyQt6.QtCore import Qt

from src.core.input_listener import InputListenerThread
from src.ui.display_overlay import OverlayManager

class IntroPage(QWizardPage):
    def __init__(self, hardware_data):
        super().__init__()
        self.setTitle("Express Multiseat Setup")
        self.setSubTitle("This wizard will help you configure additional seats.")
        
        layout = QVBoxLayout(self)
        
        gpus = len(hardware_data.get("graphics", []))
        desc = QLabel(f"Your system has {gpus} GPUs detected.\n\n"
                      "Seat 0 (the master seat) is the default environment. "
                      "We will now identify hardware for your secondary seats.")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        layout.addWidget(QLabel("How many additional seats do you want to create?"))
        self.seat_count = QSpinBox()
        self.seat_count.setRange(1, 10)
        self.seat_count.setValue(1)
        self.registerField("seat_count", self.seat_count)
        layout.addWidget(self.seat_count)

class SeatSetupPage(QWizardPage):
    def __init__(self, seat_idx, hardware_data):
        super().__init__()
        self.seat_idx = seat_idx
        self.setTitle(f"Configure seat{seat_idx}")
        self.setSubTitle(f"Identify hardware mapping to seat{seat_idx}.")
        
        self.hardware_data = hardware_data
        self.assignments = []
        
        layout = QVBoxLayout(self)
        
        # Monitor ID Placeholder
        monitor_layout = QHBoxLayout()
        monitor_layout.addWidget(QLabel("Assign a GPU/Monitor:"))
        
        self.gpu_combo = QComboBox()
        self.gpu_combo.addItem("Select a GPU...", None)
        for i, gpu in enumerate(self.hardware_data.get("graphics", [])):
            self.gpu_combo.addItem(f"GPU {i}: {gpu.get('name', 'Unknown')}", gpu.get("persistent_id"))
        self.gpu_combo.currentIndexChanged.connect(self.on_gpu_selected)
        monitor_layout.addWidget(self.gpu_combo)
        
        self.btn_identify_displays = QPushButton("Identify Displays")
        self.btn_identify_displays.setToolTip("Click to show numbers on screens")
        self.btn_identify_displays.clicked.connect(self.identify_displays)
        monitor_layout.addWidget(self.btn_identify_displays)
        layout.addLayout(monitor_layout)
        
        # Mouse / Keyboard ID Placeholder
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Assign Keyboard/Mouse:"))
        self.btn_identify_inputs = QPushButton("Click/Type on Device to Identify")
        self.btn_identify_inputs.clicked.connect(self.toggle_identify_inputs)
        input_layout.addWidget(self.btn_identify_inputs)
        layout.addLayout(input_layout)
        
        # List of Assigned HW
        layout.addWidget(QLabel("Assigned Hardware:"))
        self.assigned_list = QListWidget()
        layout.addWidget(self.assigned_list)
        
        self.assigned_list.addItem("Pending Hardware Selection...")
        
        self.listener = None
        self.overlay_manager = OverlayManager()
        
    def identify_displays(self):
        gpus = self.hardware_data.get("graphics", [])
        if gpus:
            self.overlay_manager.show_all_gpu_overlays(gpus, duration_ms=4000)

    def on_gpu_selected(self, index):
        gpu_id = self.gpu_combo.currentData()
        if not gpu_id:
            return
            
        gpu_data = next((g for g in self.hardware_data.get("graphics", []) if g.get("persistent_id") == gpu_id), None)
        if gpu_data and not any(a.get("persistent_id") == gpu_id for a in self.assignments):
            self.assignments.append(gpu_data)
            if self.assigned_list.item(0) and "Pending" in self.assigned_list.item(0).text():
                self.assigned_list.takeItem(0)
            self.assigned_list.addItem(self.gpu_combo.currentText())

    def toggle_identify_inputs(self):
        if self.listener and self.listener.isRunning():
            self.stop_listening()
        else:
            self.listener = InputListenerThread(self.hardware_data.get("inputs", []))
            self.listener.device_identified.connect(self.on_device_identified)
            self.btn_identify_inputs.setText("Listening... (Press a key/button)")
            self.listener.start()
            
    def on_device_identified(self, persistent_id):
        self.stop_listening()
        dev_name = persistent_id
        inp_data = None
        for inp in self.hardware_data.get("inputs", []):
            if inp.get("persistent_id") == persistent_id:
                dev_name = inp.get("name")
                inp_data = inp
                break
                
        if inp_data and not any(a.get("persistent_id") == persistent_id for a in self.assignments):
            self.assignments.append(inp_data)
            if self.assigned_list.item(0) and "Pending" in self.assigned_list.item(0).text():
                self.assigned_list.takeItem(0)
            self.assigned_list.addItem(dev_name)
            
    def stop_listening(self):
        if self.listener:
            self.listener.stop()
            self.listener = None
        self.btn_identify_inputs.setText("Click/Type on Device to Identify")
        
    def get_assignments(self):
        return self.assignments

class FinalPage(QWizardPage):
    def __init__(self, hardware_data):
        super().__init__()
        self.setTitle("Confirm Configuration")
        self.setSubTitle("Everything not assigned to a secondary seat will remain on seat0 (Master).")
        
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Remaining Unassigned Hardware (seat0):"))
        self.unassigned_list = QListWidget()
        # Mock populator
        for gpu in hardware_data.get("graphics", []):
            self.unassigned_list.addItem(f"GPU: {gpu.get('name')}")
            for mon in gpu.get("monitors", []):
                self.unassigned_list.addItem(f"  └─ Monitor: {mon.get('name')}")
        layout.addWidget(self.unassigned_list)
        
        layout.addWidget(QLabel("The loginctl commands will be applied on Finish."))

class ExpressSetupWizard(QWizard):
    def __init__(self, hardware_data, parent=None):
        super().__init__(parent)
        self.hardware_data = hardware_data
        self.setWindowTitle("Multiseat Express Setup")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setButtonText(QWizard.WizardButton.CancelButton, "Stop Setup")
        
        self.intro_page = IntroPage(self.hardware_data)
        self.intro_page_id = self.addPage(self.intro_page)
        
        self.seat_pages = []
        for i in range(1, 11):
            page = SeatSetupPage(i, self.hardware_data)
            self.seat_pages.append(self.addPage(page))
            
        self.final_page_id = self.addPage(FinalPage(self.hardware_data))
        
    def get_mapping(self):
        mapping = {}
        for i in range(1, self.field("seat_count") + 1):
            mapping[f"seat{i}"] = []
            
            if i <= len(self.seat_pages):
                page_id = self.seat_pages[i-1]
                page = self.page(page_id)
                if isinstance(page, SeatSetupPage):
                    mapping[f"seat{i}"] = page.get_assignments()
                    
        return mapping

    def nextId(self):
        curr = self.currentId()
        if curr == self.intro_page_id:
            count = self.field("seat_count")
            if count > 0:
                return self.seat_pages[0]
            return self.final_page_id
            
        if curr in self.seat_pages:
            idx = self.seat_pages.index(curr)
            count = self.field("seat_count")
            if idx + 1 < count:
                return self.seat_pages[idx + 1]
            return self.final_page_id
            
        return super().nextId()
