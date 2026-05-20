"""
Diagnostics tab — guided diagnostic sequence with report and fix suggestions.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QProgressBar, QTextEdit, QLabel, QGroupBox
)
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QTextCursor, QColor
from core.modem import Modem
from core import diagnostics
from core.diagnostics import SEVERITY_OK, SEVERITY_WARNING, SEVERITY_ERROR


class DiagThread(QThread):
    progress = Signal(int, int, str)
    done     = Signal(object)

    def __init__(self, modem):
        super().__init__()
        self.modem = modem

    def run(self):
        report = diagnostics.run(
            self.modem,
            progress_cb=lambda step, total, label: self.progress.emit(step, total, label)
        )
        self.done.emit(report)


class DiagnosticsWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.modem: Modem | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.run_btn = QPushButton("▶  Iniciar Diagnóstico")
        self.run_btn.setEnabled(False)
        self.run_btn.clicked.connect(self._run)
        self.run_btn.setMinimumHeight(36)
        top.addWidget(self.run_btn)
        top.addStretch()
        layout.addLayout(top)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress_label = QLabel("")
        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFontFamily("monospace")
        layout.addWidget(self.log_box, stretch=2)

        self.issues_box = QGroupBox("Problemas encontrados")
        self.issues_layout = QVBoxLayout(self.issues_box)
        self.issues_placeholder = QLabel("Nenhum diagnóstico executado.")
        self.issues_layout.addWidget(self.issues_placeholder)
        layout.addWidget(self.issues_box, stretch=1)

    def set_modem(self, modem: Modem | None):
        self.modem = modem
        self.run_btn.setEnabled(modem is not None)

    def _run(self):
        if not self.modem:
            return
        self.run_btn.setEnabled(False)
        self.log_box.clear()
        self._clear_issues()
        self.progress.setVisible(True)
        self.progress.setValue(0)

        self._thread = DiagThread(self.modem)
        self._thread.progress.connect(self._on_progress)
        self._thread.done.connect(self._on_done)
        self._thread.start()

    def _on_progress(self, step, total, label):
        self.progress.setMaximum(total)
        self.progress.setValue(step)
        self.progress_label.setText(label)
        self._append_log(f"[{step}/{total}] {label}...")

    def _on_done(self, report):
        self.run_btn.setEnabled(True)
        self.progress.setVisible(False)
        self.progress_label.setText("")

        for line in report.log:
            self._append_log(line)

        self._clear_issues()
        if not report.issues:
            lbl = QLabel("✓  Nenhum problema encontrado.")
            lbl.setStyleSheet("color: #155724; font-weight: bold;")
            self.issues_layout.addWidget(lbl)
        else:
            for issue in report.issues:
                self._add_issue_card(issue)

    def _add_issue_card(self, issue):
        colors = {
            SEVERITY_ERROR:   ("#f8d7da", "#721c24", "✗"),
            SEVERITY_WARNING: ("#fff3cd", "#856404", "⚠"),
            SEVERITY_OK:      ("#d4edda", "#155724", "✓"),
        }
        bg, fg, icon = colors.get(issue.severity, ("#e2e3e5", "#383d41", "•"))

        card = QGroupBox()
        card.setStyleSheet(f"QGroupBox {{ background:{bg}; border:1px solid {fg}; border-radius:6px; padding:4px; }}")
        card_layout = QVBoxLayout(card)

        title = QLabel(f"{icon}  {issue.title}")
        title.setStyleSheet(f"color:{fg}; font-weight:bold;")
        card_layout.addWidget(title)

        desc = QLabel(issue.description)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{fg};")
        card_layout.addWidget(desc)

        if issue.fix:
            fix = QLabel(f"→ {issue.fix}")
            fix.setWordWrap(True)
            fix.setStyleSheet(f"color:{fg}; font-style:italic;")
            card_layout.addWidget(fix)

        self.issues_layout.addWidget(card)

    def _clear_issues(self):
        while self.issues_layout.count():
            child = self.issues_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _append_log(self, text: str):
        self.log_box.append(text)
        self.log_box.moveCursor(QTextCursor.End)
