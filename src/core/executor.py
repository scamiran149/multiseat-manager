import subprocess
import os
import stat
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtWidgets import QMessageBox

from src.core.loginctl_api import get_current_assignments

class ConfigExecutor:
    def __init__(self, parent_widget=None):
        self.parent = parent_widget
        self.app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.staging_dir = os.path.join(self.app_dir, "staging")
        
    def _get_target_path(self, hw_data):
        # GPUs should attach by their base PCI path to absorb both video and audio components
        if hw_data.get("type") == "graphics" and hw_data.get("pci_syspath"):
            return hw_data.get("pci_syspath")
        return hw_data.get("syspath")

    def generate_staging(self, staging_map):
        """
        staging_map: {"seat1": [hw_data_1, hw_data_2], "seat0": [...]}
        Returns the staging directory path if rules were written, or None.
        """
        live_assignments = get_current_assignments()
        
        commands = []
        udev_rules = []
        
        for seat_name, hw_list in staging_map.items():
            for hw in hw_list:
                target_path = self._get_target_path(hw)
                if not target_path:
                    continue
                    
                current_seat = live_assignments.get(target_path, "seat0")
                if current_seat != seat_name and seat_name != "seat0":
                    commands.append(f"loginctl attach {seat_name} {target_path}")

                if seat_name != "seat0":
                    dev_name = hw.get("name", "Unknown Device")
                    devpath = target_path[4:] if target_path.startswith("/sys") else target_path
                    udev_rules.append(f"# {dev_name}")
                    udev_rules.append(f'TAG=="seat", DEVPATH=="{devpath}", ENV{{ID_SEAT}}="{seat_name}"')

        os.makedirs(self.staging_dir, exist_ok=True)
        
        script_content = "#!/bin/sh\n"
        
        rules_path = os.path.join(self.staging_dir, "70-multiseat-manager.rules")
        if udev_rules:
            with open(rules_path, "w") as f:
                f.write("\n".join(udev_rules) + "\n")
            script_content += f"cp {os.path.abspath(rules_path)} /etc/udev/rules.d/70-multiseat-manager.rules\n"
        elif os.path.exists(rules_path):
            os.remove(rules_path)
            
        if commands:
            script_content += "\n".join(commands) + "\n"
        
        script_content += "udevadm control --reload-rules\n"
        script_content += "udevadm trigger\n"
        
        script_path = os.path.join(self.staging_dir, "apply_config.sh")
        with open(script_path, "w") as f:
            f.write(script_content)
        
        st = os.stat(script_path)
        os.chmod(script_path, st.st_mode | stat.S_IEXEC)
        
        return self.staging_dir
