from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QApplication
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

class DisplayOverlay(QWidget):
    def __init__(self, text):
        super().__init__()
        # Essential flags for an invisible, unclickable, always-on-top overlay
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowOpacity(0.85)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.label = QLabel(str(text))
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet(
            "color: white; "
            "background-color: rgba(30, 100, 200, 210); "
            "border: 8px solid white; "
            "border-radius: 40px; "
            "padding: 20px;"
        )
        font = QFont("Arial", 35, QFont.Weight.Bold)
        self.label.setFont(font)
        
        layout.addWidget(self.label)
        
    def show_on_screen(self, screen_geometry):
        self.setGeometry(screen_geometry)
        self.show()

class OverlayManager:
    def __init__(self):
        self.overlays = []
        
    def show_gpu_overlays(self, gpu_data, text="Identified", duration_ms=4000):
        self.clear()
        screens = QApplication.screens()
        
        # Build a list of valid DRM connectors for this GPU
        valid_connectors = []
        gpu_name = gpu_data.get("name", "")
        for mon in gpu_data.get("monitors", []):
            syspath = mon.get("syspath", "")
            basename = syspath.split("/")[-1] # eg: card0-DP-1
            if "-" in basename:
                connector = basename.split("-", 1)[1] # DP-1
                valid_connectors.extend([connector, connector.replace("-", ""), basename])
                
        matched_screens = []
        for screen in screens:
            s_name = screen.name()
            # If QScreen matches the DRM connector alias
            if any((vc in s_name or s_name in vc) for vc in valid_connectors):
                matched_screens.append(screen)
                
        # Fallback: If we couldn't properly match the Qt string to the DRM string, 
        # spam all connected displays so the user actually sees *something*.
        if not matched_screens:
            matched_screens = screens
            
        final_text = text if text != "Identified" else f"{gpu_name}\nIdentified"
        for screen in matched_screens:
            overlay = DisplayOverlay(final_text)
            overlay.show_on_screen(screen.geometry())
            self.overlays.append(overlay)
            
        if duration_ms > 0:
            QTimer.singleShot(duration_ms, self.clear)

    def show_all_gpu_overlays(self, graphics_list, duration_ms=4000):
        self.clear()
        screens = QApplication.screens()
        
        for i, gpu in enumerate(graphics_list):
            valid_connectors = []
            for mon in gpu.get("monitors", []):
                syspath = mon.get("syspath", "")
                basename = syspath.split("/")[-1]
                if "-" in basename:
                    connector = basename.split("-", 1)[1]
                    valid_connectors.extend([connector, connector.replace("-", ""), basename])
                    
            for screen in screens:
                s_name = screen.name()
                if any((vc in s_name or s_name in vc) for vc in valid_connectors):
                    overlay = DisplayOverlay(f"GPU {i}\n{gpu.get('name', '')}")
                    overlay.show_on_screen(screen.geometry())
                    self.overlays.append(overlay)
                    
        # Fallback if Qt names absolutely mismatch DRM names
        if not self.overlays:
            for i, screen in enumerate(screens):
                overlay = DisplayOverlay(f"Display {i}")
                overlay.show_on_screen(screen.geometry())
                self.overlays.append(overlay)
                
        if duration_ms > 0:
            QTimer.singleShot(duration_ms, self.clear)

    def clear(self):
        for overlay in self.overlays:
            overlay.close()
        self.overlays.clear()
