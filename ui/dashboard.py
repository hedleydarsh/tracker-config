"""
Dashboard tab — read-only view of all modem parameters.
Auto-refreshes every 10s when connected.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QPushButton, QProgressBar, QGridLayout, QFrame
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QColor, QPalette
from core.modem import Modem


class RefreshThread(QThread):
    done = Signal(object, object, object, object)

    def __init__(self, modem):
        super().__init__()
        self.modem = modem

    def run(self):
        m = self.modem.read_modem_info()
        n = self.modem.read_network_info()
        d = self.modem.read_data_info()
        s = self.modem.read_sms_info()
        self.done.emit(m, n, d, s)


class StatusBadge(QLabel):
    """Colored pill label: green=ok, yellow=warning, red=error, gray=unknown."""
    COLORS = {
        "ok":      ("#d4edda", "#155724"),
        "warning": ("#fff3cd", "#856404"),
        "error":   ("#f8d7da", "#721c24"),
        "unknown": ("#e2e3e5", "#383d41"),
    }

    def set_status(self, text: str, kind: str = "ok"):
        bg, fg = self.COLORS.get(kind, self.COLORS["unknown"])
        self.setText(f"  {text}  ")
        self.setStyleSheet(
            f"background:{bg}; color:{fg}; border-radius:8px; padding:2px 6px; font-weight:bold;"
        )


class DashboardWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.modem: Modem | None = None
        self._timer = QTimer()
        self._timer.timeout.connect(self.refresh)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Toolbar ──────────────────────────────────────────────────
        top = QHBoxLayout()
        self.refresh_btn = QPushButton("Atualizar")
        self.refresh_btn.clicked.connect(self.refresh)
        self.refresh_btn.setEnabled(False)
        self.auto_label = QLabel("Auto-refresh: 10s")
        top.addWidget(self.refresh_btn)
        top.addWidget(self.auto_label)
        top.addStretch()
        layout.addLayout(top)

        grid = QHBoxLayout()
        layout.addLayout(grid)

        # ── Módulo ───────────────────────────────────────────────────
        mod_box = QGroupBox("Módulo")
        mod_layout = QGridLayout(mod_box)
        self._add_row(mod_layout, 0, "Modelo",   "_lbl_model")
        self._add_row(mod_layout, 1, "Firmware", "_lbl_firmware")
        self._add_row(mod_layout, 2, "IMEI",     "_lbl_imei")
        self._add_row(mod_layout, 3, "IMSI",     "_lbl_imsi")
        grid.addWidget(mod_box)

        # ── Rede ─────────────────────────────────────────────────────
        net_box = QGroupBox("Rede")
        net_layout = QGridLayout(net_box)
        self._lbl_reg = StatusBadge("—")
        net_layout.addWidget(QLabel("Status:"), 0, 0)
        net_layout.addWidget(self._lbl_reg, 0, 1)
        self._add_row(net_layout, 1, "Operadora",  "_lbl_operator")
        self._add_row(net_layout, 2, "Tecnologia", "_lbl_tech")
        net_layout.addWidget(QLabel("Sinal:"), 3, 0)
        self._signal_bar = QProgressBar()
        self._signal_bar.setRange(0, 31)
        self._signal_bar.setTextVisible(True)
        net_layout.addWidget(self._signal_bar, 3, 1)
        self._add_row(net_layout, 4, "RSRP",  "_lbl_rsrp")
        self._add_row(net_layout, 5, "Banda",  "_lbl_band")
        grid.addWidget(net_box)

        # ── Dados ────────────────────────────────────────────────────
        data_box = QGroupBox("Dados / APN")
        data_layout = QGridLayout(data_box)
        self._lbl_data_status = StatusBadge("—")
        data_layout.addWidget(QLabel("Status:"), 0, 0)
        data_layout.addWidget(self._lbl_data_status, 0, 1)
        self._add_row(data_layout, 1, "APN",  "_lbl_apn")
        self._add_row(data_layout, 2, "IP",   "_lbl_ip")
        grid.addWidget(data_box)

        # ── SMS ──────────────────────────────────────────────────────
        sms_box = QGroupBox("SMS")
        sms_layout = QGridLayout(sms_box)
        self._lbl_smsc_status = StatusBadge("—")
        sms_layout.addWidget(QLabel("SMSC:"), 0, 0)
        sms_layout.addWidget(self._lbl_smsc_status, 0, 1)
        self._add_row(sms_layout, 1, "Número SMSC", "_lbl_smsc")
        self._add_row(sms_layout, 2, "Storage",     "_lbl_sms_storage")
        grid.addWidget(sms_box)

        layout.addStretch()

    def _add_row(self, layout, row, label, attr):
        lbl = QLabel("—")
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        setattr(self, attr, lbl)
        layout.addWidget(QLabel(f"{label}:"), row, 0)
        layout.addWidget(lbl, row, 1)

    def set_modem(self, modem: Modem | None):
        self.modem = modem
        self.refresh_btn.setEnabled(modem is not None)
        if modem:
            self._timer.start(10_000)
            self.refresh()
        else:
            self._timer.stop()
            self._clear()

    def refresh(self):
        if not self.modem:
            return
        self.refresh_btn.setEnabled(False)
        self._thread = RefreshThread(self.modem)
        self._thread.done.connect(self._update)
        self._thread.start()

    def _update(self, modem_info, net_info, data_info, sms_info):
        self.refresh_btn.setEnabled(True)

        self._lbl_model.setText(modem_info.model or "—")
        self._lbl_firmware.setText(modem_info.firmware or "—")
        self._lbl_imei.setText(modem_info.imei or "—")
        self._lbl_imsi.setText(modem_info.imsi or "—")

        if net_info.registered:
            status = "Roaming" if net_info.roaming else "Registrado"
            self._lbl_reg.set_status(status, "warning" if net_info.roaming else "ok")
        else:
            self._lbl_reg.set_status("Sem registro", "error")

        self._lbl_operator.setText(net_info.operator or "—")
        self._lbl_tech.setText(net_info.technology or "—")
        self._signal_bar.setValue(net_info.csq if net_info.csq != 99 else 0)
        self._signal_bar.setFormat(f"CSQ {net_info.csq}  ({net_info.rssi_dbm} dBm)")
        self._lbl_rsrp.setText(f"{net_info.rsrp} / RSRQ {net_info.rsrq} / SINR {net_info.sinr}" if net_info.rsrp else "—")
        self._lbl_band.setText(f"{net_info.band}  EARFCN {net_info.earfcn}" if net_info.band else "—")

        if data_info.active:
            self._lbl_data_status.set_status("Ativo", "ok")
        else:
            self._lbl_data_status.set_status("Inativo", "error")
        self._lbl_apn.setText(data_info.apn or "—")
        self._lbl_ip.setText(data_info.ip or "—")

        if sms_info.smsc_utf16_bug:
            self._lbl_smsc_status.set_status("⚠ Bug UTF-16", "error")
            self._lbl_smsc.setText(f"{sms_info.smsc_decoded}  (encoded: {sms_info.smsc[:20]}...)")
        else:
            self._lbl_smsc_status.set_status("OK", "ok")
            self._lbl_smsc.setText(sms_info.smsc or "—")
        self._lbl_sms_storage.setText(
            f"{sms_info.storage}  {sms_info.storage_used}/{sms_info.storage_total}"
            if sms_info.storage_total else "—"
        )

    def _clear(self):
        for attr in ["_lbl_model","_lbl_firmware","_lbl_imei","_lbl_imsi",
                     "_lbl_operator","_lbl_tech","_lbl_rsrp","_lbl_band",
                     "_lbl_apn","_lbl_ip","_lbl_smsc","_lbl_sms_storage"]:
            getattr(self, attr).setText("—")
        self._lbl_reg.set_status("—", "unknown")
        self._lbl_data_status.set_status("—", "unknown")
        self._lbl_smsc_status.set_status("—", "unknown")
        self._signal_bar.setValue(0)
