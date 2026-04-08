import subprocess
import os
import stat
from PyQt6.QtWidgets import QMessageBox

from src.core.loginctl_api import get_current_assignments

class ConfigExecutor:
    def __init__(self, parent_widget=None):
        self.parent = parent_widget
        self.app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.staging_dir = os.path.join(self.app_dir, "staging")
        
    def _get_target_path(self, hw_data):
        # GPUs should attach by their base PCI path to absorb both video and audio components
        # Also handles 'gpu' type from UI and 'graphics' type from raw scanner
        hw_type = hw_data.get("type")
        if hw_type in ["graphics", "gpu"] and hw_data.get("pci_syspath"):
            pci_id = hw_data.get("pci_syspath")
            syspath = hw_data.get("syspath", "")

            # The pci_syspath stored by the scanner is just the base PCI ID (e.g. "0000:01:00").
            # We need to reconstruct the full sysfs path by finding where this ID exists in the full syspath.
            if pci_id in syspath:
                idx = syspath.find(pci_id) + len(pci_id)
                # We need to include the function suffix (like .0) if it exists, or just use the prefix.
                # Actually, the base PCI ID strips the .0 suffix.
                # So if syspath is `/sys/devices/.../0000:01:00.0/drm/card0`
                # And pci_id is `0000:01:00`, we want `/sys/devices/.../0000:01:00.0`
                # Let's find the ID and the next '/'
                idx = syspath.find(pci_id)
                if idx != -1:
                    end_idx = syspath.find('/', idx)
                    if end_idx != -1:
                        return syspath[:end_idx]
                    return syspath[idx:] # fallback
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
                    # In some mock testing cases, target_path might be short. Ensure it drops /sys but works either way.
                    devpath = target_path[4:] if target_path.startswith("/sys") else target_path
                    if not devpath.startswith("/"):
                        devpath = "/" + devpath
                        
                    udev_rules.append(f"# {dev_name}")

                    hw_type = hw.get("type", "")

                    mode_str = ""
                    if hw.get("restrict_access"):
                        mode_str = ', MODE="0600"'

                    udev_rules.append(f'TAG=="seat", DEVPATH=="{devpath}", ENV{{ID_SEAT}}="{seat_name}"{mode_str}')

                    # If this is a GPU using a PCI syspath, we must explicitly tag related subsystems
                    # to ensure DRM, fb, and sound cards under this PCI bus are assigned to the seat.
                    if hw_type in ["graphics", "gpu"] and hw.get("pci_syspath"):
                        # Catch children for drm, graphics and sound
                        udev_rules.append(f'TAG=="seat", DEVPATH=="{devpath}/*", SUBSYSTEM=="drm", ENV{{ID_SEAT}}="{seat_name}"')
                        udev_rules.append(f'TAG=="seat", DEVPATH=="{devpath}/*", SUBSYSTEM=="graphics", ENV{{ID_SEAT}}="{seat_name}"')
                        udev_rules.append(f'TAG=="seat", DEVPATH=="{devpath}/*", SUBSYSTEM=="sound", ENV{{ID_SEAT}}="{seat_name}"')

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
