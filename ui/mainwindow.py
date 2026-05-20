"""
Main application window — tab container with toolbar.
Tabs: Dashboard | Config | Diagnostics | AT Console
"""

from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QToolBar,
    QComboBox, QPushButton, QLabel, QStatusBar, QWidget
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon

from core.detector import find_modems
from core.modem import Modem
from ui.dashboard import DashboardWidget
from ui.config import ConfigWidget
from ui.diagnostics import DiagnosticsWidget
from ui.console import ConsoleWidget


class ScanThread(QThread):
    found = Signal(list)

    def run(self):
        modems = find_modems(stop_mm=True)
        self.found.emit(modems)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.modem: Modem | None = None
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("Tracker Config")
        self.setMinimumSize(900, 600)

        # ── Toolbar ──────────────────────────────────────────────────
        toolbar = QToolBar("Conexão")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        toolbar.addWidget(QLabel("  Porta: "))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(140)
        toolbar.addWidget(self.port_combo)

        self.scan_btn = QPushButton("Escanear")
        self.scan_btn.clicked.connect(self._scan_ports)
        toolbar.addWidget(self.scan_btn)

        self.connect_btn = QPushButton("Conectar")
        self.connect_btn.clicked.connect(self._toggle_connect)
        self.connect_btn.setEnabled(False)
        toolbar.addWidget(self.connect_btn)

        toolbar.addSeparator()
        self.status_label = QLabel("  Desconectado")
        toolbar.addWidget(self.status_label)

        # ── Tabs ─────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.dashboard    = DashboardWidget()
        self.config_panel = ConfigWidget()
        self.diagnostics  = DiagnosticsWidget()
        self.console      = ConsoleWidget()

        self.tabs.addTab(self.dashboard,    "Dashboard")
        self.tabs.addTab(self.config_panel, "Configuração")
        self.tabs.addTab(self.diagnostics,  "Diagnóstico")
        self.tabs.addTab(self.console,      "Console AT")

        # ── Status bar ───────────────────────────────────────────────
        self.setStatusBar(QStatusBar())

    # ── Slots ─────────────────────────────────────────────────────────

    def _scan_ports(self):
        self.scan_btn.setEnabled(False)
        self.scan_btn.setText("Escaneando...")
        self._scan_thread = ScanThread()
        self._scan_thread.found.connect(self._on_scan_done)
        self._scan_thread.start()

    def _on_scan_done(self, modems: list):
        self.scan_btn.setEnabled(True)
        self.scan_btn.setText("Escanear")
        self.port_combo.clear()
        for m in modems:
            label = f"{m['port']}  ({m['model'] or 'SIMCom'})"
            self.port_combo.addItem(label, userData=m['port'])
        if modems:
            self.connect_btn.setEnabled(True)
            self.statusBar().showMessage(f"{len(modems)} modem(s) encontrado(s)")
        else:
            self.connect_btn.setEnabled(False)
            self.statusBar().showMessage("Nenhum modem encontrado")

    def _toggle_connect(self):
        if self.modem and self.modem.is_connected():
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        port = self.port_combo.currentData()
        if not port:
            return
        self.modem = Modem(port)
        try:
            self.modem.connect()
            self.connect_btn.setText("Desconectar")
            self.status_label.setText(f"  Conectado: {port}")
            # propagate modem to all panels
            self.dashboard.set_modem(self.modem)
            self.config_panel.set_modem(self.modem)
            self.diagnostics.set_modem(self.modem)
            self.console.set_modem(self.modem)
        except Exception as e:
            self.statusBar().showMessage(f"Erro: {e}")
            self.modem = None

    def _disconnect(self):
        if self.modem:
            self.modem.disconnect()
            self.modem = None
        self.connect_btn.setText("Conectar")
        self.status_label.setText("  Desconectado")
        self.dashboard.set_modem(None)
        self.config_panel.set_modem(None)
        self.diagnostics.set_modem(None)
        self.console.set_modem(None)
