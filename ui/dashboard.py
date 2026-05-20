"""
Dashboard tab — live read-only view of all modem parameters.
Auto-refreshes every 10s when connected.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QGroupBox, QLabel, QPushButton, QProgressBar,
    QScrollArea, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QFont
from typing import Optional
from core.modem import Modem, ModemInfo, NetworkInfo, DataInfo, SmsInfo


class RefreshThread(QThread):
    done = Signal(object, object, object, object)

    def __init__(self, modem: Modem):
        super().__init__()
        self.modem = modem

    def run(self):
        m = self.modem.read_modem_info()
        n = self.modem.read_network_info()
        d = self.modem.read_data_info()
        s = self.modem.read_sms_info()
        self.done.emit(m, n, d, s)


class Badge(QLabel):
    """Colored status pill."""

    STYLES = {
        "ok":      ("background:#d4edda; color:#155724;", "✓"),
        "warning": ("background:#fff3cd; color:#856404;", "⚠"),
        "error":   ("background:#f8d7da; color:#721c24;", "✗"),
        "unknown": ("background:#e2e3e5; color:#495057;", "—"),
    }

    def __init__(self):
        super().__init__("  —  ")
        self.setAlignment(Qt.AlignCenter)
        self._apply("unknown", "—")

    def set(self, text: str, kind: str = "ok"):
        style, icon = self.STYLES.get(kind, self.STYLES["unknown"])
        self._apply(kind, f"{icon}  {text}")

    def _apply(self, kind: str, text: str):
        style, _ = self.STYLES.get(kind, self.STYLES["unknown"])
        self.setText(f"  {text}  ")
        self.setStyleSheet(
            f"{style} border-radius:10px; padding:2px 8px; font-weight:600;"
        )


class SignalBar(QProgressBar):
    """Signal bar that changes color by strength."""

    def __init__(self):
        super().__init__()
        self.setRange(0, 31)
        self.setValue(0)
        self.setFormat("Sem sinal")
        self.setMinimumWidth(160)
        self._set_color("gray")

    def set_csq(self, csq: int):
        if csq == 99 or csq == 0:
            self.setValue(0)
            self.setFormat("Sem sinal")
            self._set_color("gray")
            return
        self.setValue(csq)
        dbm = -113 + csq * 2
        self.setFormat(f"CSQ {csq}  ({dbm} dBm)")
        if csq >= 15:
            self._set_color("green")
        elif csq >= 8:
            self._set_color("yellow")
        else:
            self._set_color("red")

    def _set_color(self, color: str):
        colors = {
            "green":  "#28a745",
            "yellow": "#ffc107",
            "red":    "#dc3545",
            "gray":   "#adb5bd",
        }
        c = colors.get(color, "#adb5bd")
        self.setStyleSheet(
            f"QProgressBar::chunk {{ background:{c}; border-radius:3px; }}"
            "QProgressBar { border:1px solid #dee2e6; border-radius:4px; "
            "background:#f8f9fa; text-align:center; }"
        )


def _field(layout: QGridLayout, row: int, label: str, attr: str, parent) -> QLabel:
    """Add a label+value row to a grid and register the value label on parent."""
    key = QLabel(f"{label}:")
    key.setStyleSheet("color:#6c757d; font-size:12px;")
    val = QLabel("—")
    val.setTextInteractionFlags(Qt.TextSelectableByMouse)
    val.setWordWrap(True)
    layout.addWidget(key, row, 0, Qt.AlignTop)
    layout.addWidget(val, row, 1, Qt.AlignTop)
    setattr(parent, attr, val)
    return val


class DashboardWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.modem: Optional[Modem] = None
        self._timer = QTimer()
        self._timer.timeout.connect(self.refresh)
        self._thread: Optional[RefreshThread] = None
        self._setup_ui()

    # ── UI setup ──────────────────────────────────────────────────────

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 6, 8, 4)
        self.refresh_btn = QPushButton("↻  Atualizar")
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.clicked.connect(self.refresh)
        self.last_update = QLabel("Nunca atualizado")
        self.last_update.setStyleSheet("color:#6c757d; font-size:11px;")
        toolbar.addWidget(self.refresh_btn)
        toolbar.addSpacing(12)
        toolbar.addWidget(self.last_update)
        toolbar.addStretch()
        outer.addLayout(toolbar)

        # separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#dee2e6;")
        outer.addWidget(line)

        # scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        grid = QGridLayout(content)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setSpacing(12)

        grid.addWidget(self._build_module_box(),  0, 0)
        grid.addWidget(self._build_network_box(), 0, 1)
        grid.addWidget(self._build_data_box(),    1, 0)
        grid.addWidget(self._build_sms_box(),     1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

    def _box(self, title: str) -> tuple[QGroupBox, QGridLayout]:
        box = QGroupBox(title)
        box.setStyleSheet(
            "QGroupBox { font-weight:600; border:1px solid #dee2e6; "
            "border-radius:6px; margin-top:8px; padding:4px; }"
            "QGroupBox::title { subcontrol-origin:margin; left:10px; }"
        )
        layout = QGridLayout(box)
        layout.setColumnMinimumWidth(0, 100)
        layout.setColumnStretch(1, 1)
        return box, layout

    def _build_module_box(self) -> QGroupBox:
        box, lay = self._box("📦  Módulo")
        _field(lay, 0, "Modelo",   "_f_model",    self)
        _field(lay, 1, "Firmware", "_f_firmware",  self)
        _field(lay, 2, "IMEI",     "_f_imei",      self)
        _field(lay, 3, "IMSI",     "_f_imsi",      self)
        _field(lay, 4, "ICCID",    "_f_iccid",     self)
        lay.setRowStretch(5, 1)
        return box

    def _build_network_box(self) -> QGroupBox:
        box, lay = self._box("📡  Rede")
        self._b_reg = Badge()
        lay.addWidget(QLabel("Status:"), 0, 0, Qt.AlignTop)
        lay.addWidget(self._b_reg, 0, 1, Qt.AlignLeft)
        _field(lay, 1, "Operadora",  "_f_operator", self)
        _field(lay, 2, "Tecnologia", "_f_tech",      self)

        lay.addWidget(QLabel("Sinal:"), 3, 0, Qt.AlignVCenter)
        self._signal = SignalBar()
        lay.addWidget(self._signal, 3, 1)

        _field(lay, 4, "RSRP / RSRQ / SINR", "_f_rsrp",    self)
        _field(lay, 5, "Banda / EARFCN",       "_f_band",    self)
        _field(lay, 6, "Cell ID / TAC",         "_f_cell",    self)
        lay.setRowStretch(7, 1)
        return box

    def _build_data_box(self) -> QGroupBox:
        box, lay = self._box("🌐  Dados / APN")
        self._b_data = Badge()
        lay.addWidget(QLabel("Status:"), 0, 0, Qt.AlignTop)
        lay.addWidget(self._b_data, 0, 1, Qt.AlignLeft)
        _field(lay, 1, "APN",  "_f_apn", self)
        _field(lay, 2, "Tipo", "_f_apn_type", self)
        _field(lay, 3, "IP",   "_f_ip",  self)
        lay.setRowStretch(4, 1)
        return box

    def _build_sms_box(self) -> QGroupBox:
        box, lay = self._box("✉️  SMS")
        self._b_smsc = Badge()
        lay.addWidget(QLabel("SMSC:"), 0, 0, Qt.AlignTop)
        lay.addWidget(self._b_smsc, 0, 1, Qt.AlignLeft)
        _field(lay, 1, "Número SMSC",  "_f_smsc",         self)
        _field(lay, 2, "Bearer",        "_f_sms_bearer",   self)
        _field(lay, 3, "Storage",       "_f_sms_storage",  self)
        lay.setRowStretch(4, 1)
        return box

    # ── Public API ────────────────────────────────────────────────────

    def set_modem(self, modem: Optional[Modem]):
        self.modem = modem
        self.refresh_btn.setEnabled(modem is not None)
        if modem:
            self._timer.start(10_000)
            self.refresh()
        else:
            self._timer.stop()
            self._clear()

    def refresh(self):
        if not self.modem or (self._thread and self._thread.isRunning()):
            return
        self.refresh_btn.setEnabled(False)
        self.last_update.setText("Atualizando...")
        self._thread = RefreshThread(self.modem)
        self._thread.done.connect(self._update)
        self._thread.start()

    # ── Slots ─────────────────────────────────────────────────────────

    def _update(self, mi: ModemInfo, ni: NetworkInfo, di: DataInfo, si: SmsInfo):
        from datetime import datetime
        self.refresh_btn.setEnabled(True)
        self.last_update.setText(f"Atualizado: {datetime.now().strftime('%H:%M:%S')}")

        # Module
        self._f_model.setText(mi.model or "—")
        self._f_firmware.setText(mi.firmware or "—")
        self._f_imei.setText(mi.imei or "—")
        self._f_imsi.setText(mi.imsi or "—")
        self._f_iccid.setText(mi.iccid if mi.iccid and "ERROR" not in mi.iccid else "—")

        # Network
        if ni.registered:
            if ni.roaming:
                self._b_reg.set("Roaming", "warning")
            else:
                self._b_reg.set("Registrado", "ok")
        else:
            self._b_reg.set("Sem registro", "error")

        self._f_operator.setText(ni.operator or "—")
        self._f_tech.setText(ni.technology or "—")
        self._signal.set_csq(ni.csq)

        if ni.rsrp:
            self._f_rsrp.setText(f"{ni.rsrp} dBm  /  {ni.rsrq} dB  /  {ni.sinr} dB")
        else:
            self._f_rsrp.setText("—")

        if ni.band:
            self._f_band.setText(f"{ni.band}  |  EARFCN {ni.earfcn}")
        else:
            self._f_band.setText("—")

        if ni.cell_id:
            self._f_cell.setText(f"{ni.cell_id}  /  TAC {ni.tac}")
        else:
            self._f_cell.setText("—")

        # Data
        if di.active:
            self._b_data.set("Ativo", "ok")
        else:
            self._b_data.set("Inativo", "error")
        self._f_apn.setText(di.apn or "—")
        self._f_apn_type.setText(di.apn_type or "—")
        self._f_ip.setText(di.ip or "—")

        # SMS
        if si.smsc_utf16_bug:
            self._b_smsc.set("Bug UTF-16", "error")
            self._f_smsc.setText(
                f"{si.smsc_decoded}  "
                f"<span style='color:#6c757d; font-size:11px;'>"
                f"(raw: {si.smsc[:24]}...)</span>"
            )
            self._f_smsc.setTextFormat(Qt.RichText)
        elif si.smsc:
            self._b_smsc.set("OK", "ok")
            self._f_smsc.setText(si.smsc)
        else:
            self._b_smsc.set("—", "unknown")
            self._f_smsc.setText("—")

        bearers = {0: "CS only", 1: "PS only", 2: "PS preferencial", 3: "CS preferencial"}
        self._f_sms_bearer.setText(bearers.get(si.bearer, str(si.bearer)))

        if si.storage_total:
            pct = int(si.storage_used / si.storage_total * 100)
            self._f_sms_storage.setText(
                f"{si.storage}  —  {si.storage_used}/{si.storage_total} ({pct}%)"
            )
        else:
            self._f_sms_storage.setText("—")

    def _clear(self):
        fields = [
            "_f_model", "_f_firmware", "_f_imei", "_f_imsi", "_f_iccid",
            "_f_operator", "_f_tech", "_f_rsrp", "_f_band", "_f_cell",
            "_f_apn", "_f_apn_type", "_f_ip", "_f_smsc",
            "_f_sms_bearer", "_f_sms_storage",
        ]
        for attr in fields:
            getattr(self, attr).setText("—")
        for badge in (self._b_reg, self._b_data, self._b_smsc):
            badge.set("—", "unknown")
        self._signal.set_csq(0)
        self.last_update.setText("Nunca atualizado")
