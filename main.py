#!/usr/bin/env python3
"""
tracker-config — Desktop configurator for SIMCom-based GPS trackers
Entry point
"""

import sys
from PySide6.QtWidgets import QApplication
from ui.mainwindow import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Tracker Config")
    app.setApplicationVersion("0.1.0")
    app.setOrganizationName("hedley")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
