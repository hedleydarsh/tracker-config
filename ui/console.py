"""
AT Console tab — raw terminal for manual AT commands with history and log.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QTextEdit, QLabel, QCheckBox
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QTextCursor, QFont, QColor
from datetime import datetime
from core.modem import Modem


class CmdThread(QThread):
    done = Signal(str, str)

    def __init__(self, modem, cmd):
        super().__init__()
        self.modem = modem
        self.cmd   = cmd

    def run(self):
        resp = self.modem.send(self.cmd, 2.0)
        self.done.emit(self.cmd, resp)


class ConsoleWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.modem: Modem | None = None
        self._history: list[str] = []
        self._history_idx = -1
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # ── Log area ─────────────────────────────────────────────────
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        font = QFont("Courier New", 10)
        font.setStyleHint(QFont.Monospace)
        self.log.setFont(font)
        self.log.setStyleSheet("background: #1e1e1e; color: #d4d4d4;")
        layout.addWidget(self.log)

        # ── Input bar ────────────────────────────────────────────────
        bottom = QHBoxLayout()

        self.input = QLineEdit()
        self.input.setPlaceholderText("Digite um comando AT (ex: AT+CSQ)")
        self.input.setFont(font)
        self.input.returnPressed.connect(self._send)
        self.input.installEventFilter(self)
        self.input.setEnabled(False)
        bottom.addWidget(self.input)

        self.send_btn = QPushButton("Enviar")
        self.send_btn.clicked.connect(self._send)
        self.send_btn.setEnabled(False)
        bottom.addWidget(self.send_btn)

        self.clear_btn = QPushButton("Limpar")
        self.clear_btn.clicked.connect(self.log.clear)
        bottom.addWidget(self.clear_btn)

        layout.addLayout(bottom)

        # ── Quick commands ────────────────────────────────────────────
        quick = QHBoxLayout()
        quick.addWidget(QLabel("Rápidos:"))
        for cmd in ["ATI", "AT+CSQ", "AT+CEREG?", "AT+COPS?", "AT+CGACT?", "AT+CSCA?"]:
            btn = QPushButton(cmd)
            btn.setMaximumWidth(100)
            btn.clicked.connect(lambda _, c=cmd: self._run_cmd(c))
            quick.addWidget(btn)
        quick.addStretch()
        layout.addLayout(quick)

        self._quick_btns = [
            w for w in self.findChildren(QPushButton)
            if w not in (self.send_btn, self.clear_btn)
        ]

    def set_modem(self, modem: Modem | None):
        self.modem = modem
        self.input.setEnabled(modem is not None)
        self.send_btn.setEnabled(modem is not None)
        for btn in self._quick_btns:
            btn.setEnabled(modem is not None)
        if modem:
            self._log_system("Conectado. Digite comandos AT abaixo.")
        else:
            self._log_system("Desconectado.")

    def _send(self):
        cmd = self.input.text().strip()
        if not cmd or not self.modem:
            return
        self._history.append(cmd)
        self._history_idx = len(self._history)
        self.input.clear()
        self._run_cmd(cmd)

    def _run_cmd(self, cmd: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._append(f'<span style="color:#569cd6">[{ts}] ► {cmd}</span>')
        self.input.setEnabled(False)
        self.send_btn.setEnabled(False)

        self._thread = CmdThread(self.modem, cmd)
        self._thread.done.connect(self._on_response)
        self._thread.start()

    def _on_response(self, cmd: str, resp: str):
        color = "#ce9178" if "ERROR" in resp else "#6a9955" if "OK" in resp else "#d4d4d4"
        for line in resp.splitlines():
            if line.strip():
                self._append(f'<span style="color:{color}">  {line}</span>')
        self.input.setEnabled(True)
        self.send_btn.setEnabled(True)
        self.input.setFocus()

    def _log_system(self, msg: str):
        self._append(f'<span style="color:#888">── {msg} ──</span>')

    def _append(self, html: str):
        self.log.append(html)
        self.log.moveCursor(QTextCursor.End)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        from PySide6.QtGui import QKeyEvent
        if obj is self.input and event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_Up and self._history:
                self._history_idx = max(0, self._history_idx - 1)
                self.input.setText(self._history[self._history_idx])
            elif key == Qt.Key_Down:
                self._history_idx = min(len(self._history), self._history_idx + 1)
                self.input.setText(
                    self._history[self._history_idx]
                    if self._history_idx < len(self._history) else ""
                )
        return super().eventFilter(obj, event)
