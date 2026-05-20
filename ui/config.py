"""
Config tab — set APN, SMSC, network mode, SMS storage, send test SMS.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QComboBox, QPushButton, QLabel,
    QHBoxLayout, QMessageBox
)
from PySide6.QtCore import QThread, Signal, Qt
from core.modem import Modem


class WorkerThread(QThread):
    done   = Signal(bool, str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            result = self._fn()
            self.done.emit(True, str(result))
        except Exception as e:
            self.done.emit(False, str(e))


class ConfigWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.modem: Modem | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)

        # ── APN ──────────────────────────────────────────────────────
        apn_box = QGroupBox("APN / Dados")
        apn_form = QFormLayout(apn_box)

        self.apn_input = QLineEdit()
        self.apn_input.setPlaceholderText("ex: timbrasil.br")
        apn_form.addRow("APN:", self.apn_input)

        self.apn_type = QComboBox()
        self.apn_type.addItems(["IP", "IPV4V6"])
        apn_form.addRow("Tipo:", self.apn_type)

        self.apn_btn = QPushButton("Aplicar APN")
        self.apn_btn.clicked.connect(self._apply_apn)
        self.apn_btn.setEnabled(False)
        apn_form.addRow("", self.apn_btn)
        layout.addWidget(apn_box)

        # ── SMSC ─────────────────────────────────────────────────────
        smsc_box = QGroupBox("SMSC (Central de SMS)")
        smsc_form = QFormLayout(smsc_box)

        self.smsc_input = QLineEdit()
        self.smsc_input.setPlaceholderText("ex: +5511818110000")
        smsc_form.addRow("SMSC:", self.smsc_input)

        smsc_note = QLabel(
            "⚠ Em módulos com firmware LSOFTSIM o AT+CSCA é bloqueado.\n"
            "Use 'Enviar SMS de teste' para verificar via PDU."
        )
        smsc_note.setStyleSheet("color: #856404; font-size: 11px;")
        smsc_note.setWordWrap(True)
        smsc_form.addRow("", smsc_note)

        self.smsc_btn = QPushButton("Aplicar SMSC")
        self.smsc_btn.clicked.connect(self._apply_smsc)
        self.smsc_btn.setEnabled(False)
        smsc_form.addRow("", self.smsc_btn)
        layout.addWidget(smsc_box)

        # ── Modo de rede ─────────────────────────────────────────────
        net_box = QGroupBox("Modo de Rede")
        net_form = QFormLayout(net_box)

        self.net_mode = QComboBox()
        self.net_mode.addItem("Automático",  2)
        self.net_mode.addItem("LTE only",   38)
        self.net_mode.addItem("GSM only",   13)
        self.net_mode.addItem("GSM + LTE",  51)
        net_form.addRow("Modo:", self.net_mode)

        self.net_btn = QPushButton("Aplicar modo")
        self.net_btn.clicked.connect(self._apply_network_mode)
        self.net_btn.setEnabled(False)
        net_form.addRow("", self.net_btn)
        layout.addWidget(net_box)

        # ── SMS ──────────────────────────────────────────────────────
        sms_box = QGroupBox("SMS")
        sms_form = QFormLayout(sms_box)

        self.sms_storage = QComboBox()
        self.sms_storage.addItem("ME — Memória interna (180 slots)", "ME")
        self.sms_storage.addItem("SM — SIM card (5-50 slots)",       "SM")
        sms_form.addRow("Storage:", self.sms_storage)

        self.sms_storage_btn = QPushButton("Aplicar storage")
        self.sms_storage_btn.clicked.connect(self._apply_sms_storage)
        self.sms_storage_btn.setEnabled(False)
        sms_form.addRow("", self.sms_storage_btn)

        sms_form.addRow(QLabel(""))
        sms_form.addRow(QLabel("Teste de envio SMS (PDU com SMSC embutido):"))

        self.sms_dest = QLineEdit()
        self.sms_dest.setPlaceholderText("+5511999999999")
        sms_form.addRow("Destino:", self.sms_dest)

        self.sms_smsc_override = QLineEdit()
        self.sms_smsc_override.setPlaceholderText("SMSC para o PDU (ex: +551181138200)")
        sms_form.addRow("SMSC PDU:", self.sms_smsc_override)

        self.sms_send_btn = QPushButton("Enviar SMS de teste")
        self.sms_send_btn.clicked.connect(self._send_test_sms)
        self.sms_send_btn.setEnabled(False)
        sms_form.addRow("", self.sms_send_btn)

        layout.addWidget(sms_box)

        # ── Reset ────────────────────────────────────────────────────
        rst_box = QGroupBox("Reset")
        rst_layout = QHBoxLayout(rst_box)

        self.rf_reset_btn = QPushButton("Reset de Rádio (CFUN)")
        self.rf_reset_btn.clicked.connect(self._rf_reset)
        self.rf_reset_btn.setEnabled(False)
        rst_layout.addWidget(self.rf_reset_btn)

        self.factory_btn = QPushButton("Factory Reset (AT&F)")
        self.factory_btn.clicked.connect(self._factory_reset)
        self.factory_btn.setEnabled(False)
        rst_layout.addWidget(self.factory_btn)

        layout.addWidget(rst_box)
        layout.addStretch()

    def set_modem(self, modem: Modem | None):
        self.modem = modem
        enabled = modem is not None
        for btn in [self.apn_btn, self.smsc_btn, self.net_btn,
                    self.sms_storage_btn, self.sms_send_btn,
                    self.rf_reset_btn, self.factory_btn]:
            btn.setEnabled(enabled)

    def _run_worker(self, fn, success_msg: str):
        self.setEnabled(False)
        self._worker = WorkerThread(fn)
        def on_done(ok, msg):
            self.setEnabled(True)
            if ok:
                QMessageBox.information(self, "Sucesso", success_msg)
            else:
                QMessageBox.critical(self, "Erro", msg)
        self._worker.done.connect(on_done)
        self._worker.start()

    def _apply_apn(self):
        apn  = self.apn_input.text().strip()
        typ  = self.apn_type.currentText()
        if not apn:
            return
        self._run_worker(
            lambda: self.modem.set_apn(apn, pdp_type=typ),
            f"APN '{apn}' configurado com sucesso."
        )

    def _apply_smsc(self):
        smsc = self.smsc_input.text().strip()
        if not smsc:
            return
        self._run_worker(
            lambda: self.modem.set_smsc(smsc),
            f"SMSC '{smsc}' configurado."
        )

    def _apply_network_mode(self):
        mode = self.net_mode.currentData()
        self._run_worker(
            lambda: self.modem.set_network_mode(mode),
            f"Modo de rede alterado para '{self.net_mode.currentText()}'."
        )

    def _apply_sms_storage(self):
        storage = self.sms_storage.currentData()
        self._run_worker(
            lambda: self.modem.set_sms_storage(storage),
            f"Storage SMS alterado para {storage}."
        )

    def _send_test_sms(self):
        dest = self.sms_dest.text().strip()
        smsc = self.sms_smsc_override.text().strip()
        if not dest or not smsc:
            QMessageBox.warning(self, "Atenção", "Preencha Destino e SMSC PDU.")
            return
        self._run_worker(
            lambda: self.modem.send_sms(dest, "Teste TrackerConfig", smsc),
            f"SMS enviado para {dest}."
        )

    def _rf_reset(self):
        reply = QMessageBox.question(self, "Confirmar", "Executar reset de rádio (CFUN cycle)?")
        if reply == QMessageBox.Yes:
            self._run_worker(lambda: self.modem.reset_rf(), "Reset de rádio concluído.")

    def _factory_reset(self):
        reply = QMessageBox.question(self, "Confirmar", "Executar factory reset (AT&F)?")
        if reply == QMessageBox.Yes:
            self._run_worker(lambda: self.modem.factory_reset(), "Factory reset concluído.")
