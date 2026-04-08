from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
    QTreeWidget, QTreeWidgetItem, QScrollArea, QAbstractItemView, QPushButton,
    QTreeWidgetItemIterator, QMenu
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QAction

from src.core.input_listener import InputListenerThread
from src.ui.display_overlay import OverlayManager
from src.core.executor import ConfigExecutor
from src.core.backup import save_configuration, load_configuration
from src.ui.review_dialog import ReviewDialog

class DraggableTree(QTreeWidget):
    def __init__(self, title, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.setHeaderLabel(title)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
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

    def show_context_menu(self, pos):
        item = self.itemAt(pos)
        if not item or not item.parent():
            return # Don't show menu for empty space or top-level group nodes
            
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data or not data.get("type"):
            return
            
        hw_type = data.get("type")
        hw_data = data.get("hw", {})
        
        # Only show menu for top-level draggable items
        if hw_type not in ["gpu", "usb_hub", "usb_child", "input", "av"]:
            return

        menu = QMenu(self)
        
        if hw_type == "input":
            restrict_action = QAction("Restrict Access (0600)", self)
            restrict_action.setCheckable(True)
            restrict_action.setChecked(hw_data.get("restrict_access", False))
            restrict_action.triggered.connect(lambda checked, i=item, h=hw_data: self.toggle_restrict_access(i, h, checked))
            menu.addAction(restrict_action)
            menu.addSeparator()
            
        if self.main_window:
            move_menu = menu.addMenu("Move to...")
            for tree in self.main_window.get_all_trees():
                target_seat = tree.headerItem().text(0)
                # Don't show current seat
                if target_seat == self.headerItem().text(0):
                    continue
                    
                action = QAction(target_seat, self)
                action.triggered.connect(lambda checked, tgt=tree, i=item: self.move_item_to_tree(i, tgt))
                move_menu.addAction(action)

        menu.exec(self.mapToGlobal(pos))
        
    def toggle_restrict_access(self, item, hw_data, is_restricted):
        hw_data["restrict_access"] = is_restricted
        
        # Explicitly update the item data to ensure changes persist (avoids copy issues)
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data:
            data["hw"] = hw_data
            item.setData(0, Qt.ItemDataRole.UserRole, data)

        current_text = item.text(0)
        if is_restricted and not current_text.endswith(" 🔒"):
            item.setText(0, f"{current_text} 🔒")
        elif not is_restricted and current_text.endswith(" 🔒"):
            item.setText(0, current_text[:-2])
            
    def move_item_to_tree(self, item, target_tree):
        source_parent = item.parent()
        if not source_parent:
            return
            
        data = item.data(0, Qt.ItemDataRole.UserRole)
        hw_type = data.get("type")
        
        target_group = {
            "gpu": target_tree.grp_graphics,
            "usb_hub": target_tree.grp_usb,
            "usb_child": target_tree.grp_usb,
            "input": target_tree.grp_inputs,
            "av": target_tree.grp_av,
        }.get(hw_type)
        
        if target_group:
            index = source_parent.indexOfChild(item)
            taken_item = source_parent.takeChild(index)
            target_group.addChild(taken_item)

    def dropEvent(self, event):
        source = event.source()
        if not source or not hasattr(source, 'currentItem'):
            event.ignore()
            return

        source_item = source.currentItem()
        if not source_item:
            event.ignore()
            return

        data = source_item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            event.ignore()
            return

        hw_type = data.get("type")
        if not hw_type:
            event.ignore()
            return

        # Determine the target group
        target_group = {
            "gpu": self.grp_graphics,
            "usb_hub": self.grp_usb,
            "usb_child": self.grp_usb,
            "input": self.grp_inputs,
            "av": self.grp_av,
        }.get(hw_type)

        if not target_group:
            # Monitors or audio nested under monitors/gpus shouldn't be dragged independently
            event.ignore()
            return

        # Remove from source
        source_parent = source_item.parent()
        if source_parent:
            # Recreate the item to avoid issues with parent taking ownership
            # PyQt QTreeWidget drag and drop can be finicky with just changing parents
            # But takeChild works fine for moving across trees

            # Let the default implementation handle visual feedback, but intercept the actual drop
            # Actually, standard QTreeWidget dropEvent moves the item to the position where mouse released.
            # We want to force it to a specific group node.

            # Remove item from old parent
            index = source_parent.indexOfChild(source_item)
            item = source_parent.takeChild(index)

            # Add to proper group
            target_group.addChild(item)

            # Accept event but tell Qt we handled the action to avoid default drop behavior
            event.setDropAction(Qt.DropAction.IgnoreAction)
            event.accept()
        else:
            event.ignore()

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

        self.seat0_tree = DraggableTree("seat0 (Master)", main_window=self)
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
        btn_apply.setStyleSheet("background-color: #2b579a; color: white; font-weight: bold; padding: 10px;")
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
                
            # Normalize identifiers to strings (they could be dicts from wizard/load or strings from live_mapping)
            normalized_ids = []
            for ident in identifiers:
                if isinstance(ident, dict):
                    normalized_ids.append(ident.get("id") or ident.get("persistent_id") or ident.get("syspath"))
                elif isinstance(ident, str):
                    normalized_ids.append(ident)
                
            items_to_move = []
            
            def find_matching_items(parent_item):
                for i in range(parent_item.childCount()):
                    child = parent_item.child(i)
                    hw_data = child.data(0, Qt.ItemDataRole.UserRole).get("hw", {}) if child.data(0, Qt.ItemDataRole.UserRole) else {}
                    pid = hw_data.get("persistent_id")
                    syspath = hw_data.get("syspath")
                    pci_syspath = hw_data.get("pci_syspath")
                    
                    match = False
                    matched_ident_obj = None
                    for ident in identifiers:
                        # Extract string value for matching
                        ident_str = ""
                        if isinstance(ident, dict):
                            ident_str = ident.get("id") or ident.get("persistent_id") or ident.get("syspath")
                        elif isinstance(ident, str):
                            ident_str = ident
                            
                        if not ident_str:
                            continue
                            
                        if pid == ident_str or syspath == ident_str or pci_syspath == ident_str:
                            match = True
                            matched_ident_obj = ident
                            break
                        if syspath and (ident_str.startswith(syspath) or syspath.startswith(ident_str)):
                            match = True
                            matched_ident_obj = ident
                            break
                        if pci_syspath and (ident_str.startswith(pci_syspath) or pci_syspath.startswith(ident_str)):
                            match = True
                            matched_ident_obj = ident
                            break
                        if pid and (pid.endswith(ident_str) or ident_str.endswith(pid)):
                            match = True
                            matched_ident_obj = ident
                            break
                                
                    if match:
                        # Restore restrict_access state if it came from a profile load
                        if isinstance(matched_ident_obj, dict) and matched_ident_obj.get("restrict_access"):
                            target_tree.toggle_restrict_access(child, hw_data, True)
                            
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
            
            def extract_hw(parent_item):
                for i in range(parent_item.childCount()):
                    child = parent_item.child(i)
                    data = child.data(0, Qt.ItemDataRole.UserRole)
                    if data and data.get("type") in ["gpu", "usb_hub", "usb_child", "input", "av"]:
                        staging_map[seat_name].append(data.get("hw", {}))
                    # Recurse to find nested top-level types (like usb_child under usb_hub)
                    extract_hw(child)

            # Extract from all groups in this tree
            for grp in [tree.grp_graphics, tree.grp_inputs, tree.grp_av, tree.grp_usb]:
                extract_hw(grp)
                    
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
        
        new_seat = DraggableTree(name, main_window=self)
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
