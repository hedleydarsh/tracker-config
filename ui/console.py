"""
AT Console tab — raw terminal with dark theme, command history and quick commands.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QTextEdit, QLabel, QFrame
)
from PySide6.QtCore import Qt, QThread, Signal, QEvent
from PySide6.QtGui import QTextCursor, QFont, QKeyEvent
from datetime import datetime
from typing import Optional
from core.modem import Modem

QUICK_CMDS = [
    "ATI", "AT+CSQ", "AT+CEREG?", "AT+COPS?",
    "AT+CGACT?", "AT+CSCA?", "AT+CPSI?", "AT+CGPADDR=1",
]


class CmdThread(QThread):
    done = Signal(str, str)

    def __init__(self, modem: Modem, cmd: str):
        super().__init__()
        self.modem = modem
        self.cmd   = cmd

    def run(self):
        resp = self.modem.send(self.cmd, 2.0)
        self.done.emit(self.cmd, resp)


class ConsoleWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.modem: Optional[Modem] = None
        self._history: list[str] = []
        self._history_idx: int   = -1
        self._quick_btns: list[QPushButton] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        mono = QFont("Courier New", 10)
        mono.setStyleHint(QFont.Monospace)

        # ── Log area ─────────────────────────────────────────────────
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(mono)
        self._log.setStyleSheet(
            "background:#1e1e1e; color:#d4d4d4; "
            "border:1px solid #333; border-radius:4px;"
        )
        layout.addWidget(self._log)

        # ── Input bar ────────────────────────────────────────────────
        input_row = QHBoxLayout()

        self._prompt = QLabel("►")
        self._prompt.setStyleSheet("color:#569cd6; font-weight:bold; font-size:13px;")
        input_row.addWidget(self._prompt)

        self._input = QLineEdit()
        self._input.setFont(mono)
        self._input.setPlaceholderText("Digite um comando AT  (↑↓ para histórico)")
        self._input.setStyleSheet(
            "background:#252526; color:#d4d4d4; border:1px solid #444; "
            "border-radius:4px; padding:4px;"
        )
        self._input.returnPressed.connect(self._send)
        self._input.setEnabled(False)
        self._input.installEventFilter(self)
        input_row.addWidget(self._input)

        self._send_btn = QPushButton("Enviar")
        self._send_btn.setEnabled(False)
        self._send_btn.clicked.connect(self._send)
        input_row.addWidget(self._send_btn)

        self._clear_btn = QPushButton("Limpar")
        self._clear_btn.clicked.connect(self._log.clear)
        input_row.addWidget(self._clear_btn)

        layout.addLayout(input_row)

        # ── Quick commands ────────────────────────────────────────────
        quick_row = QHBoxLayout()
        quick_row.addWidget(QLabel("Rápidos:"))

        for cmd in QUICK_CMDS:
            btn = QPushButton(cmd)
            btn.setMaximumWidth(110)
            btn.setEnabled(False)
            btn.setStyleSheet("font-size:11px;")
            btn.clicked.connect(lambda _, c=cmd: self._run_cmd(c))
            quick_row.addWidget(btn)
            self._quick_btns.append(btn)

        quick_row.addStretch()
        layout.addLayout(quick_row)

    # ── Public API ────────────────────────────────────────────────────

    def set_modem(self, modem: Optional[Modem]):
        self.modem = modem
        enabled = modem is not None
        self._input.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)
        for btn in self._quick_btns:
            btn.setEnabled(enabled)
        if modem:
            self._log_sys("Conectado — aguardando comandos.")
        else:
            self._log_sys("Desconectado.")

    # ── Slots ─────────────────────────────────────────────────────────

    def _send(self):
        cmd = self._input.text().strip()
        if not cmd or not self.modem:
            return
        if not self._history or self._history[-1] != cmd:
            self._history.append(cmd)
        self._history_idx = len(self._history)
        self._input.clear()
        self._run_cmd(cmd)

    def _run_cmd(self, cmd: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._append(
            f'<span style="color:#569cd6">[{ts}]</span> '
            f'<span style="color:#dcdcaa; font-weight:bold;">► {cmd}</span>'
        )
        self._set_input_enabled(False)

        thread = CmdThread(self.modem, cmd)
        thread.done.connect(self._on_response)
        thread.start()
        self._cmd_thread = thread

    def _on_response(self, cmd: str, resp: str):
        if not resp or not resp.strip():
            self._append('<span style="color:#888;">  (sem resposta)</span>')
        else:
            for line in resp.splitlines():
                line = line.strip()
                if not line:
                    continue
                if "ERROR" in line:
                    color = "#f44747"
                elif "OK" == line:
                    color = "#6a9955"
                elif line.startswith("+") or line.startswith("*"):
                    color = "#9cdcfe"
                else:
                    color = "#d4d4d4"
                self._append(f'<span style="color:{color};">  {line}</span>')

        self._set_input_enabled(True)
        self._input.setFocus()

    # ── Helpers ───────────────────────────────────────────────────────

    def _log_sys(self, msg: str):
        self._append(f'<span style="color:#888; font-style:italic;">── {msg} ──</span>')

    def _append(self, html: str):
        self._log.append(html)
        self._log.moveCursor(QTextCursor.End)

    def _set_input_enabled(self, enabled: bool):
        self._input.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)
        for btn in self._quick_btns:
            btn.setEnabled(enabled)

    def eventFilter(self, obj, event):
        if obj is self._input and event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_Up:
                if self._history:
                    self._history_idx = max(0, self._history_idx - 1)
                    self._input.setText(self._history[self._history_idx])
                return True
            elif key == Qt.Key_Down:
                self._history_idx = min(len(self._history), self._history_idx + 1)
                self._input.setText(
                    self._history[self._history_idx]
                    if self._history_idx < len(self._history) else ""
                )
                return True
        return super().eventFilter(obj, event)
