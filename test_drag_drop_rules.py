import sys
import unittest
from unittest.mock import MagicMock

# Attempt to load PyQT
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from src.ui.advanced_ui import AdvancedSetupWindow
from src.core.executor import ConfigExecutor

import src.core.loginctl_api

app = QApplication(sys.argv)

class MockDropEvent:
    def __init__(self, source_item):
        self._source_item = source_item
        self._accepted = False
        self._drop_action = Qt.DropAction.MoveAction

    def source(self):
        class SourceMock:
            def currentItem(self_inner):
                return self._source_item
        return SourceMock()

    def ignore(self):
        self._accepted = False

    def accept(self):
        self._accepted = True

    def setDropAction(self, action):
        self._drop_action = action

class TestDragDropToRules(unittest.TestCase):
    def setUp(self):
        self.hw_data = {
            "graphics": [{"name": "Mock GPU", "type": "graphics", "syspath": "/sys/devices/pci1/gpu1/drm/card0", "pci_syspath": "/sys/devices/pci1/gpu1"}],
            "inputs": [{"name": "Mock Input", "type": "input", "syspath": "/sys/devices/pci1/usb1/input1", "persistent_id": "input-1-id"}],
        }
        # mock current assignments empty
        src.core.loginctl_api.get_current_assignments = lambda: {}
        self.win = AdvancedSetupWindow(self.hw_data)

    def test_drag_drop_and_generate_rules(self):
        # 1. Initially all items are in seat0
        trees = self.win.get_all_trees()
        seat0 = trees[0]
        seat1 = trees[1]

        self.assertEqual(seat0.grp_graphics.childCount(), 1)
        self.assertEqual(seat0.grp_inputs.childCount(), 1)
        self.assertEqual(seat1.grp_graphics.childCount(), 0)
        self.assertEqual(seat1.grp_inputs.childCount(), 0)

        gpu_item = seat0.grp_graphics.child(0)
        input_item = seat0.grp_inputs.child(0)

        # 2. Simulate dragging gpu_item to seat1
        event1 = MockDropEvent(gpu_item)
        seat1.dropEvent(event1)
        self.assertTrue(event1._accepted)

        # 3. Simulate dragging input_item to seat1
        event2 = MockDropEvent(input_item)
        seat1.dropEvent(event2)
        self.assertTrue(event2._accepted)

        # Verify they moved
        self.assertEqual(seat0.grp_graphics.childCount(), 0)
        self.assertEqual(seat0.grp_inputs.childCount(), 0)
        self.assertEqual(seat1.grp_graphics.childCount(), 1)
        self.assertEqual(seat1.grp_inputs.childCount(), 1)

        # 4. Generate staging config using the exact logic from the UI apply step
        staging_map = {}
        for tree in self.win.get_all_trees():
            seat_name = tree.headerItem().text(0)
            if seat_name == "seat0 (Master)":
                seat_name = "seat0"
            staging_map[seat_name] = []
            for grp in [tree.grp_graphics, tree.grp_inputs, tree.grp_av, tree.grp_usb]:
                for i in range(grp.childCount()):
                    hw_data = grp.child(i).data(0, Qt.ItemDataRole.UserRole).get("hw", {})
                    # Need to patch type if missing to match how the UI does it
                    hw_type = grp.child(i).data(0, Qt.ItemDataRole.UserRole).get("type", "")
                    hw_data["type"] = hw_type
                    staging_map[seat_name].append(hw_data)

        executor = ConfigExecutor()
        staging_dir = executor.generate_staging(staging_map)

        with open(f"{staging_dir}/70-multiseat-manager.rules", "r") as f:
            rules = f.read()

        # Verify rules include the correct PCI syspath tagging for GPU and the nested DRM|sound tag
        self.assertIn('DEVPATH=="/devices/pci1/gpu1"', rules)
        self.assertIn('DEVPATH=="/devices/pci1/gpu1/*", SUBSYSTEM=="drm"', rules)
        self.assertIn('DEVPATH=="/devices/pci1/gpu1/*", SUBSYSTEM=="graphics"', rules)
        self.assertIn('DEVPATH=="/devices/pci1/gpu1/*", SUBSYSTEM=="sound"', rules)
        # Verify input rule exists
        self.assertIn('DEVPATH=="/devices/pci1/usb1/input1"', rules)

if __name__ == '__main__':
    unittest.main()
