import json
import os
from PyQt6.QtWidgets import QFileDialog, QMessageBox

def save_configuration(parent_widget, staging_map):
    """
    Serializes a seat mapping dict into a saveable JSON config file.
    Only stores the permanent IDs of the mapped devices.
    """
    export_data = {}
    for seat, hw_list in staging_map.items():
        export_data[seat] = []
        for hw in hw_list:
            # Prefer persistent string matching where possible over syspath which can fluctuate on reboot
            ident = hw.get("persistent_id") or hw.get("syspath")
            if ident:
                export_data[seat].append(ident)
                
    file_path, _ = QFileDialog.getSaveFileName(
        parent_widget, 
        "Save Multiseat Profile", 
        os.path.expanduser("~"), 
        "JSON Files (*.json);;All Files (*)"
    )
    if not file_path:
        return
        
    try:
        if not file_path.endswith(".json"):
            file_path += ".json"
        with open(file_path, "w") as f:
            json.dump(export_data, f, indent=4)
        QMessageBox.information(parent_widget, "Saved", f"Profile successfully saved to:\n{file_path}")
    except Exception as e:
        QMessageBox.critical(parent_widget, "Save Error", f"Failed to save profile:\n{str(e)}")


def load_configuration(parent_widget):
    """
    Prompts user for a JSON file, deserializes it, 
    and returns a mapping dictionary ready for apply_mapping()
    """
    file_path, _ = QFileDialog.getOpenFileName(
        parent_widget, 
        "Load Multiseat Profile", 
        os.path.expanduser("~"), 
        "JSON Files (*.json);;All Files (*)"
    )
    if not file_path:
        return None
        
    try:
        with open(file_path, "r") as f:
            mapping = json.load(f)
        return mapping
    except Exception as e:
        QMessageBox.critical(parent_widget, "Load Error", f"Failed to load profile:\n{str(e)}")
        return None
