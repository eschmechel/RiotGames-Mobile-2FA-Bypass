import sys

from PyQt6.QtWidgets import QApplication

from app.styles import load_stylesheet
from app.ui import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(load_stylesheet())
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
