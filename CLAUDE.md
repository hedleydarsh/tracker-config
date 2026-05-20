# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Desktop GUI application to detect, read and configure GPS trackers based on SIMCom A7670SA (LTE Cat-1) modules connected via USB serial. Built with Python + PySide6 (Qt6) for Linux/Windows.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python3 main.py

# Run on Linux (requires dialout group or stopped ModemManager)
sudo systemctl stop ModemManager
sg dialout -c "python3 main.py"

# Package for Linux
pyinstaller --onefile --windowed --name tracker-config main.py

# Package for Windows (run on Windows)
pyinstaller --onefile --windowed --name tracker-config.exe main.py
```

## Architecture

The app is split into two layers with no circular dependencies:

**`core/`** — pure serial/AT logic, no Qt imports allowed
- `modem.py` — single `Modem` class wrapping pyserial. All AT commands go through `Modem.send()`. Unsolicited result codes (URCs) are stripped from responses and forwarded to `urc_callback`. `send_sms()` builds a full GSM PDU with the SMSC embedded — this bypasses the SMSC UTF-16 bug present in LSOFTSIM firmware.
- `detector.py` — scans USB ports, stops ModemManager on Linux, identifies SIMCom modems via `ATI` response.
- `diagnostics.py` — runs a structured 5-step check sequence and returns a `DiagnosticReport` with typed `DiagnosticIssue` entries (severity + fix suggestion). Does not modify modem state.

**`ui/`** — PySide6 widgets, one file per tab
- `mainwindow.py` — toolbar (port scan + connect/disconnect) + `QTabWidget`. Owns the single `Modem` instance and distributes it to all tabs via `set_modem()`.
- `dashboard.py` — read-only display, auto-refreshes every 10s via `QTimer`. Uses `RefreshThread(QThread)` to avoid blocking the UI. `StatusBadge` is a reusable colored label.
- `config.py` — all write operations. Each button spawns a `WorkerThread` and disables the entire widget during execution.
- `diagnostics.py` — runs `core/diagnostics.run()` in `DiagThread`, shows progress bar and renders issue cards with severity colors.
- `console.py` — raw AT terminal with dark theme, command history (↑/↓), and quick-command buttons.

## Key domain knowledge

**SMSC UTF-16 bug**: Firmware `LSOFTSIM` (e.g. `A7670M6_SDK_CUS_CZJ_LSOFTSIM_231213`) returns SMSC via `AT+CSCA` as UTF-16BE hex instead of ASCII, and blocks writes. `Modem.read_sms_info()` detects this by checking if the raw value is all-hex with even 4-char groups. The fix is `Modem.send_sms()` which embeds the SMSC directly in the PDU (first field of GSM 03.40 PDU).

**ModemManager conflict**: On Linux, `ModemManager` holds all `/dev/ttyUSB*` ports. `detector.stop_modem_manager()` calls `sudo systemctl stop ModemManager` before scanning. This requires the user to be in the `sudo` group or have passwordless sudo for this command. Add user to `dialout` group for persistent access.

**Threading model**: `Modem._lock` (threading.Lock) serializes all serial I/O. Qt workers subclass `QThread` and emit signals — never call Qt widgets from worker threads.

**Port names**: Linux = `/dev/ttyUSB*`, Windows = `COM*`. `detector.list_candidate_ports()` handles both via `sys.platform`.

## Planned phases

- **Phase 1** (current): Core architecture + all 4 tabs stubbed
- **Phase 2**: Functional dashboard with live refresh
- **Phase 3**: Config tab — APN, SMSC, network mode
- **Phase 4**: Diagnostics tab — full sequence + issue cards
- **Phase 5**: Console tab — history, quick buttons
- **Phase 6**: Windows packaging + COM port support
