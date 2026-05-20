"""
Config tab — set APN, SMSC, network mode, SMS storage, send test SMS.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QComboBox, QPushButton, QLabel,
    QMessageBox, QScrollArea, QFrame, QSizePolicy
)
from PySide6.QtCore import QThread, Signal, Qt
from typing import Optional
from core.modem import Modem


# ── Presets ──────────────────────────────────────────────────────────────────

APN_PRESETS = [
    ("",                       "— Selecionar preset —"),
    ("timbrasil.br",           "TIM Brasil"),
    ("EM",                     "TIM M2M"),
    ("claro.com.br",           "Claro"),
    ("zap.vivo.com.br",        "Vivo"),
    ("gprs.oi.com.br",         "Oi"),
    ("em.MNC005.MCC295.GPRS",  "emnify (TrackPlus M2M)"),
]

SMSC_PRESETS = [
    ("",               "— Selecionar preset —"),
    ("+5511818110000", "TIM Brasil"),
    ("+551181138200",  "TIM M2M (decodificado)"),
    ("+5511986080808", "Claro"),
    ("+5511913160005", "Vivo"),
    ("+42379010570",   "emnify (TrackPlus M2M)"),
]


# ── Worker thread ─────────────────────────────────────────────────────────────

class WorkerThread(QThread):
    done = Signal(bool, str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            result = self._fn()
            ok = result is not False
            self.done.emit(ok, "" if ok else "Operação retornou falso")
        except Exception as e:
            self.done.emit(False, str(e))


# ── Config widget ─────────────────────────────────────────────────────────────

class ConfigWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.modem: Optional[Modem] = None
        self._worker: Optional[WorkerThread] = None
        self._action_btns: list[QPushButton] = []
        self._setup_ui()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(content)

        layout.addWidget(self._build_apn_box())
        layout.addWidget(self._build_smsc_box())
        layout.addWidget(self._build_network_box())
        layout.addWidget(self._build_sms_box())
        layout.addWidget(self._build_reset_box())

        # ── Status bar ───────────────────────────────────────────────
        self._status = QLabel("")
        self._status.setStyleSheet("color:#6c757d; font-size:11px; padding:4px 12px;")
        outer.addWidget(self._status)

        self._set_buttons_enabled(False)

    # ── Box builders ──────────────────────────────────────────────────

    def _box(self, title: str) -> tuple[QGroupBox, QFormLayout]:
        box = QGroupBox(title)
        box.setStyleSheet(
            "QGroupBox { font-weight:600; border:1px solid #dee2e6; "
            "border-radius:6px; margin-top:8px; padding:6px; }"
            "QGroupBox::title { subcontrol-origin:margin; left:10px; }"
        )
        return box, QFormLayout(box)

    def _action_btn(self, label: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setMinimumHeight(30)
        self._action_btns.append(btn)
        return btn

    def _build_apn_box(self) -> QGroupBox:
        box, form = self._box("🌐  APN / Dados")

        self._apn_preset = QComboBox()
        for val, label in APN_PRESETS:
            self._apn_preset.addItem(label, val)
        self._apn_preset.currentIndexChanged.connect(self._on_apn_preset)
        form.addRow("Preset:", self._apn_preset)

        self._apn_input = QLineEdit()
        self._apn_input.setPlaceholderText("ex: timbrasil.br")
        form.addRow("APN:", self._apn_input)

        self._apn_type = QComboBox()
        self._apn_type.addItems(["IP", "IPV4V6"])
        form.addRow("Tipo:", self._apn_type)

        btn = self._action_btn("Aplicar APN")
        btn.clicked.connect(self._apply_apn)
        form.addRow("", btn)
        return box

    def _build_smsc_box(self) -> QGroupBox:
        box, form = self._box("✉️  SMSC (Central de SMS)")

        self._smsc_preset = QComboBox()
        for val, label in SMSC_PRESETS:
            self._smsc_preset.addItem(label, val)
        self._smsc_preset.currentIndexChanged.connect(self._on_smsc_preset)
        form.addRow("Preset:", self._smsc_preset)

        self._smsc_input = QLineEdit()
        self._smsc_input.setPlaceholderText("ex: +5511818110000")
        form.addRow("SMSC:", self._smsc_input)

        note = QLabel(
            "⚠  Firmware LSOFTSIM bloqueia AT+CSCA. "
            "Use 'Enviar SMS de teste' para validar via PDU."
        )
        note.setStyleSheet("color:#856404; font-size:11px;")
        note.setWordWrap(True)
        form.addRow("", note)

        btn = self._action_btn("Aplicar SMSC")
        btn.clicked.connect(self._apply_smsc)
        form.addRow("", btn)
        return box

    def _build_network_box(self) -> QGroupBox:
        box, form = self._box("📡  Modo de Rede")

        self._net_mode = QComboBox()
        self._net_mode.addItem("Automático",  2)
        self._net_mode.addItem("LTE only",   38)
        self._net_mode.addItem("GSM only",   13)
        self._net_mode.addItem("GSM + LTE",  51)
        form.addRow("Modo:", self._net_mode)

        btn = self._action_btn("Aplicar modo")
        btn.clicked.connect(self._apply_network_mode)
        form.addRow("", btn)
        return box

    def _build_sms_box(self) -> QGroupBox:
        box, form = self._box("💬  SMS")

        self._sms_storage = QComboBox()
        self._sms_storage.addItem("ME — Memória interna (180 slots)", "ME")
        self._sms_storage.addItem("SM — SIM card (5-50 slots)",       "SM")
        form.addRow("Storage:", self._sms_storage)

        btn_storage = self._action_btn("Aplicar storage")
        btn_storage.clicked.connect(self._apply_sms_storage)
        form.addRow("", btn_storage)

        form.addRow(_separator())
        form.addRow(QLabel("<b>Teste de envio SMS</b> (PDU com SMSC embutido — bypassa bug UTF-16):"))

        self._sms_dest = QLineEdit()
        self._sms_dest.setPlaceholderText("+5511999999999")
        form.addRow("Destino:", self._sms_dest)

        self._sms_smsc = QLineEdit()
        self._sms_smsc.setPlaceholderText("SMSC para o PDU  ex: +551181138200")
        form.addRow("SMSC PDU:", self._sms_smsc)

        btn_send = self._action_btn("▶  Enviar SMS de teste")
        btn_send.clicked.connect(self._send_test_sms)
        form.addRow("", btn_send)
        return box

    def _build_reset_box(self) -> QGroupBox:
        box, form = self._box("⚙️  Reset")
        row = QHBoxLayout()

        btn_rf = self._action_btn("Reset de Rádio (CFUN)")
        btn_rf.clicked.connect(self._rf_reset)
        row.addWidget(btn_rf)

        btn_f = self._action_btn("Factory Reset (AT&F)")
        btn_f.clicked.connect(self._factory_reset)
        row.addWidget(btn_f)

        form.addRow(row)
        return box

    # ── Public API ────────────────────────────────────────────────────

    def set_modem(self, modem: Optional[Modem]):
        self.modem = modem
        self._set_buttons_enabled(modem is not None)
        if not modem:
            self._status.setText("")

    # ── Slots: presets ────────────────────────────────────────────────

    def _on_apn_preset(self, idx: int):
        val = self._apn_preset.itemData(idx)
        if val:
            self._apn_input.setText(val)

    def _on_smsc_preset(self, idx: int):
        val = self._smsc_preset.itemData(idx)
        if val:
            self._smsc_input.setText(val)

    # ── Slots: apply ──────────────────────────────────────────────────

    def _apply_apn(self):
        apn = self._apn_input.text().strip()
        typ = self._apn_type.currentText()
        if not apn:
            self._warn("Digite o APN.")
            return
        self._run(
            lambda: self.modem.set_apn(apn, pdp_type=typ),
            f"APN '{apn}' configurado."
        )

    def _apply_smsc(self):
        smsc = self._smsc_input.text().strip()
        if not smsc.startswith("+"):
            self._warn("SMSC inválido. Use formato internacional: +5511...")
            return
        self._run(
            lambda: self.modem.set_smsc(smsc),
            f"SMSC '{smsc}' configurado."
        )

    def _apply_network_mode(self):
        mode = self._net_mode.currentData()
        name = self._net_mode.currentText()
        self._run(
            lambda: self.modem.set_network_mode(mode),
            f"Modo de rede: {name}."
        )

    def _apply_sms_storage(self):
        storage = self._sms_storage.currentData()
        self._run(
            lambda: self.modem.set_sms_storage(storage),
            f"Storage SMS: {storage}."
        )

    def _send_test_sms(self):
        dest = self._sms_dest.text().strip()
        smsc = self._sms_smsc.text().strip()
        if not dest:
            self._warn("Digite o número de destino.")
            return
        if not smsc.startswith("+"):
            self._warn("Digite o SMSC PDU no formato +55...")
            return
        self._run(
            lambda: self.modem.send_sms(dest, "Teste TrackerConfig OK", smsc),
            f"SMS enviado para {dest}."
        )

    def _rf_reset(self):
        if QMessageBox.question(self, "Confirmar", "Executar reset de rádio?") == QMessageBox.Yes:
            self._run(lambda: self.modem.reset_rf(), "Reset de rádio concluído.")

    def _factory_reset(self):
        if QMessageBox.question(self, "Confirmar", "Executar factory reset (AT&F)?") == QMessageBox.Yes:
            self._run(lambda: self.modem.factory_reset(), "Factory reset concluído.")

    # ── Worker ────────────────────────────────────────────────────────

    def _run(self, fn, success_msg: str):
        self._set_buttons_enabled(False)
        self._status.setText("⏳  Executando...")

        self._worker = WorkerThread(fn)

        def on_done(ok: bool, err: str):
            self._set_buttons_enabled(True)
            if ok:
                self._status.setText(f"✓  {success_msg}")
                self._status.setStyleSheet("color:#155724; font-size:11px; padding:4px 12px;")
            else:
                self._status.setText(f"✗  Erro: {err}")
                self._status.setStyleSheet("color:#721c24; font-size:11px; padding:4px 12px;")
                QMessageBox.critical(self, "Erro", err)

        self._worker.done.connect(on_done)
        self._worker.start()

    # ── Helpers ───────────────────────────────────────────────────────

    def _set_buttons_enabled(self, enabled: bool):
        for btn in self._action_btns:
            btn.setEnabled(enabled)

    def _warn(self, msg: str):
        self._status.setText(f"⚠  {msg}")
        self._status.setStyleSheet("color:#856404; font-size:11px; padding:4px 12px;")


def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet("color:#dee2e6;")
    return line
