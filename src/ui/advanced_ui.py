from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
    QTreeWidget, QTreeWidgetItem, QScrollArea, QAbstractItemView, QPushButton,
    QTreeWidgetItemIterator
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor

from src.core.input_listener import InputListenerThread
from src.ui.display_overlay import OverlayManager
from src.core.executor import ConfigExecutor
from src.core.backup import save_configuration, load_configuration
from src.ui.review_dialog import ReviewDialog

class DraggableTree(QTreeWidget):
    def __init__(self, title):
        super().__init__()
        self.setHeaderLabel(title)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        self.grp_graphics = QTreeWidgetItem(self, ["🖥️ Graphics & Displays"])
        self.grp_graphics.setFlags(self.grp_graphics.flags() & ~Qt.ItemFlag.ItemIsDragEnabled & ~Qt.ItemFlag.ItemIsDropEnabled)
        self.grp_graphics.setExpanded(True)
        
        self.grp_inputs = QTreeWidgetItem(self, ["⌨️ Input Devices"])
        self.grp_inputs.setFlags(self.grp_inputs.flags() & ~Qt.ItemFlag.ItemIsDragEnabled & ~Qt.ItemFlag.ItemIsDropEnabled)
        self.grp_inputs.setExpanded(True)
        
        self.grp_usb = QTreeWidgetItem(self, ["🔌 USB Hubs & Raw Devices"])
        self.grp_usb.setFlags(self.grp_usb.flags() & ~Qt.ItemFlag.ItemIsDragEnabled & ~Qt.ItemFlag.ItemIsDropEnabled)
        self.grp_usb.setExpanded(False)
        
        self.grp_av = QTreeWidgetItem(self, ["🎙️ Audio & Cameras"])
        self.grp_av.setFlags(self.grp_av.flags() & ~Qt.ItemFlag.ItemIsDragEnabled & ~Qt.ItemFlag.ItemIsDropEnabled)
        self.grp_av.setExpanded(True)

    def add_gpu(self, gpu_data):
        gpu_item = QTreeWidgetItem(self.grp_graphics, [gpu_data.get("name")])
        gpu_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "gpu", "hw": gpu_data})
        for mon in gpu_data.get("monitors", []):
            mon_item = QTreeWidgetItem(gpu_item, [f"📺 {mon.get('name')}"])
            mon_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "monitor", "hw": mon})
            
            # Nested Audio under Monitor
            for av in mon.get("audio_video", []):
                av_item = QTreeWidgetItem(mon_item, [f"🔊 {av.get('name')}"])
                av_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "audio", "hw": av})
            mon_item.setExpanded(True)
                
        for av in gpu_data.get("audio_video", []):
            av_item = QTreeWidgetItem(gpu_item, [f"🔊 {av.get('name')}"])
            av_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "audio", "hw": av})
        gpu_item.setExpanded(True)

    def add_usb_hub(self, hub_data):
        if hub_data.get("hidden_by_input"):
            return
        hub_item = QTreeWidgetItem(self.grp_usb, [hub_data.get("name")])
        hub_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "usb_hub", "hw": hub_data})
        for child in hub_data.get("children", []):
            self._add_usb_child(hub_item, child)

    def _add_usb_child(self, parent_item, child_data):
        if child_data.get("hidden_by_input"):
            return
        child_item = QTreeWidgetItem(parent_item, [child_data.get("name")])
        child_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "usb_child", "hw": child_data})
        for grandchild in child_data.get("children", []):
            self._add_usb_child(child_item, grandchild)
            
    def add_input(self, input_data):
        if "error" in input_data:
            return
        inp_item = QTreeWidgetItem(self.grp_inputs, [input_data.get("name")])
        inp_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "input", "hw": input_data})
        
    def add_av(self, av_data):
        av_item = QTreeWidgetItem(self.grp_av, [av_data.get("name")])
        av_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "av", "hw": av_data})


class AdvancedSetupWindow(QMainWindow):
    def __init__(self, hardware_data, on_wizard_request=None, initial_mapping=None):
        super().__init__()
        self.hardware_data = hardware_data
        self.on_wizard_request = on_wizard_request
        self.initial_mapping = initial_mapping or {}
        self.setWindowTitle("Multiseat Manager - Advanced Manual Setup")
        self.resize(1000, 600)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        self.seat0_tree = DraggableTree("seat0 (Master)")
        self._populate_initial_hardware(self.seat0_tree)
        
        seat0_layout = QVBoxLayout()
        seat0_layout.addWidget(self.seat0_tree)
        main_layout.addLayout(seat0_layout, stretch=1)

        # Secondary Seats - Scrollable Horizontal Area
        self.secondary_scroll = QScrollArea()
        self.secondary_scroll.setWidgetResizable(True)
        self.secondary_scroll_content = QWidget()
        self.secondary_layout = QHBoxLayout(self.secondary_scroll_content)
        self.secondary_scroll.setWidget(self.secondary_scroll_content)
        
        main_layout.addWidget(self.secondary_scroll, stretch=2)

        # Controls column on the right edge
        control_layout = QVBoxLayout()
        
        btn_wizard = QPushButton("Launch Express Setup Wizard")
        btn_wizard.setStyleSheet("font-weight: bold; background-color: #2b579a; color: white; padding: 10px;")
        if self.on_wizard_request:
            btn_wizard.clicked.connect(self.on_wizard_request)
        else:
            btn_wizard.hide()

        btn_add_seat = QPushButton("+ Add Seat")
        btn_add_seat.clicked.connect(self.add_seat_column)
        
        self.overlay_manager = OverlayManager()
        self.input_listener = None
        
        btn_identify_mon = QPushButton("Identify Displays")
        btn_identify_mon.clicked.connect(self.identify_displays)
        
        self.btn_identify_inp = QPushButton("Listen for Input")
        self.btn_identify_inp.clicked.connect(self.toggle_input_listener)
        
        btn_apply = QPushButton("Apply Configuration")
        btn_apply.setStyleSheet("background-color: #2b579a; color: white; padding: 10px;")
        btn_apply.clicked.connect(self.apply_configuration)
        
        btn_save = QPushButton("Save Config...")
        btn_save.clicked.connect(self.save_config)
        
        btn_load = QPushButton("Load Config...")
        btn_load.clicked.connect(self.load_config)
        
        control_layout.addWidget(btn_wizard)
        control_layout.addSpacing(20)
        control_layout.addWidget(btn_add_seat)
        control_layout.addStretch()
        control_layout.addWidget(btn_identify_mon)
        control_layout.addWidget(self.btn_identify_inp)
        control_layout.addWidget(btn_save)
        control_layout.addWidget(btn_load)
        control_layout.addSpacing(10)
        control_layout.addWidget(btn_apply)
        main_layout.addLayout(control_layout)
        
        # Add seat1 by default
        self.seat_count = 0
        if self.initial_mapping:
            for seat_name, _ in self.initial_mapping.items():
                if seat_name.startswith("seat") and seat_name != "seat0":
                    self.add_seat_column(title=seat_name)
        else:
            self.add_seat_column()
            
        if self.initial_mapping:
            self.apply_mapping(self.initial_mapping)

    def apply_mapping(self, mapping_dict):
        """Moves items from seat0 to their target seats based on persistent_id or syspath."""
        for seat_name, identifiers in mapping_dict.items():
            if seat_name == "seat_count" or seat_name == "seat0":
                continue
                
            # Find the tree for this seat
            target_tree = None
            for tree in self.get_all_trees():
                if tree.headerItem().text(0) == seat_name:
                    target_tree = tree
                    break
            
            if not target_tree:
                continue
                
            items_to_move = []
            
            def find_matching_items(parent_item):
                for i in range(parent_item.childCount()):
                    child = parent_item.child(i)
                    hw_data = child.data(0, Qt.ItemDataRole.UserRole).get("hw", {}) if child.data(0, Qt.ItemDataRole.UserRole) else {}
                    pid = hw_data.get("persistent_id")
                    syspath = hw_data.get("syspath")
                    pci_syspath = hw_data.get("pci_syspath")
                    
                    match = False
                    if pid in identifiers or syspath in identifiers or pci_syspath in identifiers:
                        match = True
                    elif syspath:
                        for ident in identifiers:
                            if ident.startswith(syspath) or syspath.startswith(ident):
                                match = True
                                break
                    elif pci_syspath:
                        for ident in identifiers:
                            if ident.startswith(pci_syspath) or pci_syspath.startswith(ident):
                                match = True
                                break
                                
                    if match:
                        items_to_move.append((parent_item, child, target_tree))
                    else:
                        find_matching_items(child)
            
            for grp in [self.seat0_tree.grp_graphics, self.seat0_tree.grp_inputs, self.seat0_tree.grp_av, self.seat0_tree.grp_usb]:
                find_matching_items(grp)
                        
            for src_grp, item, tgt_tree in items_to_move:
                src_grp.removeChild(item)
                hw_type = item.data(0, Qt.ItemDataRole.UserRole).get("type")
                if hw_type == "gpu":
                    tgt_tree.grp_graphics.addChild(item)
                elif hw_type == "usb_hub":
                    tgt_tree.grp_usb.addChild(item)
                elif hw_type == "av":
                    tgt_tree.grp_av.addChild(item)
                else:
                    tgt_tree.grp_inputs.addChild(item)

    def get_all_trees(self):
        trees = [self.seat0_tree]
        for i in range(self.secondary_layout.count()):
            widget = self.secondary_layout.itemAt(i).widget()
            if widget:
                # the widget is a container containing the DraggableTree inside a QVBoxLayout
                tree = widget.findChild(DraggableTree)
                if tree:
                    trees.append(tree)
        return trees

    def identify_displays(self):
        selected_item = None
        for tree in self.get_all_trees():
            if tree.selectedItems():
                selected_item = tree.selectedItems()[0]
                break
                
        if selected_item:
            hw_data = selected_item.data(0, Qt.ItemDataRole.UserRole)
            if hw_data and hw_data.get("type") == "gpu":
                self.overlay_manager.show_gpu_overlays(hw_data.get("hw"))
                return
                
        # Fallback: Identify everything for user
        gpus = self.hardware_data.get("graphics", [])
        if gpus:
            self.overlay_manager.show_all_gpu_overlays(gpus)

    def toggle_input_listener(self):
        if self.input_listener and self.input_listener.isRunning():
            self.input_listener.stop()
            self.input_listener = None
            self.btn_identify_inp.setText("Listen for Input")
            self.btn_identify_inp.setStyleSheet("")
        else:
            self.input_listener = InputListenerThread(self.hardware_data.get("inputs", []))
            self.input_listener.device_identified.connect(self.on_device_identified)
            self.input_listener.start()
            self.btn_identify_inp.setText("Listening... (Press Key)")
            self.btn_identify_inp.setStyleSheet("background-color: #d15c5c; color: white; padding: 10px;")
            
    def on_device_identified(self, persistent_id):
        # Stop listening after one hit
        self.toggle_input_listener()
        
        # Look across all trees to map the source item
        for tree in self.get_all_trees():
            iterator = QTreeWidgetItemIterator(tree)
            while iterator.value():
                item = iterator.value()
                data = item.data(0, Qt.ItemDataRole.UserRole)
                if data and data.get("type") == "input":
                    if data.get("hw", {}).get("persistent_id") == persistent_id:
                        tree.setCurrentItem(item)
                        # brief visual highlight flash
                        orig_bg = item.background(0)
                        item.setBackground(0, QColor("#e0f7fa"))
                        QTimer.singleShot(1500, lambda i=item, bg=orig_bg: i.setBackground(0, bg))
                        return
                iterator += 1


    def apply_configuration(self):
        staging_map = {}
        for tree in self.get_all_trees():
            seat_name = tree.headerItem().text(0)
            if seat_name == "seat0 (Master)":
                seat_name = "seat0"
                
            staging_map[seat_name] = []
            
            # Extract top-level items assigned to this seat
            for grp in [tree.grp_graphics, tree.grp_inputs, tree.grp_av, tree.grp_usb]:
                for i in range(grp.childCount()):
                    hw_data = grp.child(i).data(0, Qt.ItemDataRole.UserRole).get("hw", {})
                    staging_map[seat_name].append(hw_data)
                    
        executor = ConfigExecutor(parent_widget=self)
        staging_dir = executor.generate_staging(staging_map)
        if staging_dir:
            dialog = ReviewDialog(staging_dir, self)
            dialog.exec()

    def save_config(self):
        staging_map = {}
        for tree in self.get_all_trees():
            seat_name = tree.headerItem().text(0)
            if seat_name == "seat0 (Master)":
                seat_name = "seat0"
            staging_map[seat_name] = []
            for grp in [tree.grp_graphics, tree.grp_inputs, tree.grp_av, tree.grp_usb]:
                for i in range(grp.childCount()):
                    hw_data = grp.child(i).data(0, Qt.ItemDataRole.UserRole).get("hw", {})
                    staging_map[seat_name].append(hw_data)
        save_configuration(self, staging_map)
        
    def load_config(self):
        new_map = load_configuration(self)
        if new_map:
            for seat in new_map.keys():
                if seat != "seat0" and not any(tree.headerItem().text(0) == seat for tree in self.get_all_trees()):
                    self.add_seat_column(seat)
            self.apply_mapping(new_map)

    def _populate_initial_hardware(self, tree):
        for gpu in self.hardware_data.get("graphics", []):
            tree.add_gpu(gpu)
            
        for hub_id, hub_data in self.hardware_data.get("usb", {}).items():
            tree.add_usb_hub(hub_data)
            
        for inp in self.hardware_data.get("inputs", []):
            if not inp.get("error"):
                tree.add_input(inp)
                
        for av in self.hardware_data.get("av", []):
            tree.add_av(av)
                
    def add_seat_column(self, title=None):
        self.seat_count += 1
        name = title if title else f"seat{self.seat_count}"
        
        seat_container = QWidget()
        seat_layout = QVBoxLayout(seat_container)
        seat_layout.setContentsMargins(0, 0, 0, 0)
        
        new_seat = DraggableTree(name)
        seat_layout.addWidget(new_seat)
        
        btn_clear = QPushButton("Clear Seat")
        btn_clear.clicked.connect(lambda checked, tree=new_seat: self.clear_seat(tree))
        seat_layout.addWidget(btn_clear)
        
        self.secondary_layout.addWidget(seat_container)

    def clear_seat(self, source_tree):
        """Moves all top-level device nodes from the configured seat back to seat0 (Master)"""
        # We must iterate backwards or capture items to avoid index shifting during takeover
        items_to_move = []
        for grp in [source_tree.grp_graphics, source_tree.grp_inputs, source_tree.grp_av, source_tree.grp_usb]:
            for i in range(grp.childCount()):
                items_to_move.append((grp, grp.child(i)))
                
        for grp, item in items_to_move:
            grp.removeChild(item)
            
            # Map it back to the corresponding group in seat0
            item_data = item.data(0, Qt.ItemDataRole.UserRole)
            if not item_data:
                continue
                
            hw_type = item_data.get("type")
            if hw_type == "gpu":
                self.seat0_tree.grp_graphics.addChild(item)
            elif hw_type == "usb_hub":
                self.seat0_tree.grp_usb.addChild(item)
            elif hw_type == "av":
                self.seat0_tree.grp_av.addChild(item)
            else:
                self.seat0_tree.grp_inputs.addChild(item)
