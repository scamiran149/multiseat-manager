import os
import stat
from PyQt6.QtWidgets import QMessageBox

def install_desktop_file(parent_widget=None):
    """
    Creates a .desktop file in ~/.local/share/applications/ allowing the
    Multiseat Manager to be launched directly from the user's application menu.
    """
    # Define absolute paths based on the script's execution context
    app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    # Launch directly via the bash bootstrapper so the venv is activated automatically
    exec_cmd = os.path.join(app_dir, "launch.sh")

    desktop_content = f"""[Desktop Entry]
Name=Multiseat Manager
Comment=Configure loginctl multiseat hardware assignments dynamically.
Exec={exec_cmd}
Icon=preferences-desktop-peripherals
Terminal=false
Type=Application
Categories=Qt;KDE;Settings;HardwareSettings;System;
Keywords=multiseat;loginctl;seat;hardware;usb;gpu;
"""

    desktop_dir = os.path.expanduser("~/.local/share/applications")
    os.makedirs(desktop_dir, exist_ok=True)
    
    desktop_file = os.path.join(desktop_dir, "multiseat-manager.desktop")
    
    try:
        with open(desktop_file, "w") as f:
            f.write(desktop_content)
            
        # Make the .desktop file executable (some DEs require this for safety)
        st = os.stat(desktop_file)
        os.chmod(desktop_file, st.st_mode | stat.S_IEXEC)
        
        # Poke the desktop environment to refresh its app cache
        os.system("update-desktop-database ~/.local/share/applications/ > /dev/null 2>&1")
        
        if parent_widget:
            QMessageBox.information(parent_widget, "Installed", f"Desktop shortcut successfully installed to:\n{desktop_file}")
            
    except Exception as e:
        if parent_widget:
            QMessageBox.critical(parent_widget, "Install Error", f"Failed to create .desktop shortcut:\n{str(e)}")
