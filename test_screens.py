import sys
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
for s in QApplication.screens():
    print(f"Screen: name='{s.name()}', geom={s.geometry()}")
