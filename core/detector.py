"""
USB port detector — finds SIMCom modems on Linux and Windows.
Stops ModemManager on Linux if it's holding the port.
"""

import sys
import subprocess
import serial
import serial.tools.list_ports
import time
from typing import List


def list_candidate_ports() -> List[str]:
    """Return all USB serial ports available on the system."""
    ports = []
    for p in serial.tools.list_ports.comports():
        name = p.device
        if sys.platform == "win32":
            if name.startswith("COM"):
                ports.append(name)
        else:
            if "ttyUSB" in name or "ttyACM" in name:
                ports.append(name)
    return sorted(ports)


def stop_modem_manager() -> bool:
    """Stop ModemManager on Linux (it holds USB serial ports)."""
    if sys.platform == "win32":
        return True
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "ModemManager"],
            capture_output=True, text=True
        )
        if result.stdout.strip() == "active":
            subprocess.run(
                ["sudo", "systemctl", "stop", "ModemManager"],
                capture_output=True
            )
            time.sleep(1.0)
        return True
    except Exception:
        return False


def probe_port(port: str, baudrate: int = 115200, timeout: float = 2.0) -> dict | None:
    """
    Try to open a port and identify a SIMCom modem via ATI.
    Returns a dict with model/firmware/imei, or None if not a SIMCom modem.
    """
    try:
        ser = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(0.3)

        ser.reset_input_buffer()
        ser.write(b"ATE0\r\n")
        time.sleep(0.3)
        ser.read_all()

        ser.reset_input_buffer()
        ser.write(b"ATI\r\n")
        time.sleep(1.5)
        raw = ser.read_all().decode(errors="replace")
        ser.close()

        if not raw or "ERROR" in raw:
            return None

        # Must identify as SIMCom A76xx or compatible
        if not any(kw in raw for kw in ["A7670", "A7680", "A7600", "SIM7600", "SIMCOM", "INCORPORATED"]):
            return None

        info = {"port": port, "model": "", "firmware": "", "imei": ""}
        for line in raw.splitlines():
            if "Model:" in line:
                info["model"] = line.split("Model:")[1].strip()
            elif "Revision:" in line:
                info["firmware"] = line.split("Revision:")[1].strip()
            elif "IMEI:" in line:
                info["imei"] = line.split("IMEI:")[1].strip()
        return info

    except (serial.SerialException, OSError):
        return None


def find_modems(stop_mm: bool = True) -> List[dict]:
    """
    Scan all candidate ports and return list of detected SIMCom modems.
    On Linux, optionally stops ModemManager first.
    """
    if stop_mm and sys.platform != "win32":
        stop_modem_manager()

    candidates = list_candidate_ports()
    modems = []
    for port in candidates:
        result = probe_port(port)
        if result:
            modems.append(result)
    return modems
