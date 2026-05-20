"""
Modem AT command interface — SIMCom A7670SA (and compatible)
All serial communication goes through this module.
"""

import serial
import time
import threading
from dataclasses import dataclass, field
from typing import Optional, Callable


@dataclass
class ModemInfo:
    port: str = ""
    model: str = ""
    firmware: str = ""
    imei: str = ""
    imsi: str = ""
    iccid: str = ""
    msisdn: str = ""


@dataclass
class NetworkInfo:
    registered: bool = False
    roaming: bool = False
    operator: str = ""
    technology: str = ""
    csq: int = 0
    rssi_dbm: int = 0
    rsrp: int = 0
    rsrq: int = 0
    sinr: int = 0
    band: str = ""
    earfcn: str = ""
    cell_id: str = ""
    tac: str = ""


@dataclass
class DataInfo:
    apn: str = ""
    apn_type: str = ""
    active: bool = False
    ip: str = ""


@dataclass
class SmsInfo:
    smsc: str = ""
    smsc_utf16_bug: bool = False
    smsc_decoded: str = ""
    service: str = ""
    bearer: int = 3
    storage: str = ""
    storage_used: int = 0
    storage_total: int = 0


class Modem:
    """
    Wraps pyserial for AT command communication.
    All public methods are thread-safe via _lock.
    Unsolicited result codes (URCs) are dispatched via urc_callback.
    """

    def __init__(self, port: str, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self._ser: Optional[serial.Serial] = None
        self._lock = threading.Lock()
        self.urc_callback: Optional[Callable[[str], None]] = None

    # ── Connection ────────────────────────────────────────────────────

    def connect(self) -> bool:
        self._ser = serial.Serial(self.port, self.baudrate, timeout=3)
        time.sleep(0.3)
        self.send("ATE0", 0.3)
        self.send("AT+CMEE=2", 0.3)
        self.send("AT+CREG=0", 0.3)
        self.send("AT+CGREG=0", 0.3)
        self.send("AT+CEREG=0", 0.3)
        return True

    def disconnect(self):
        if self._ser and self._ser.is_open:
            self._ser.close()

    def is_connected(self) -> bool:
        return self._ser is not None and self._ser.is_open

    # ── Core AT ───────────────────────────────────────────────────────

    def send(self, cmd: str, delay: float = 2.0) -> str:
        """Send AT command and return full response."""
        with self._lock:
            if not self._ser or not self._ser.is_open:
                return ""
            self._ser.reset_input_buffer()
            self._ser.write((cmd + "\r\n").encode())
            time.sleep(delay)
            raw = self._ser.read_all().decode(errors="replace").strip()
            return self._strip_urcs(raw)

    def _strip_urcs(self, raw: str) -> str:
        """Remove unsolicited result code lines from response."""
        urc_prefixes = [
            "*BANDIND", "*COPN", "+CSCON", "+CGREG", "+CREG",
            "+CNETCI", "*REJCAUSE", "+MSTK", "*ISIMAID",
        ]
        lines = raw.splitlines()
        clean, urcs = [], []
        for line in lines:
            if any(line.strip().startswith(p) for p in urc_prefixes):
                urcs.append(line)
            else:
                clean.append(line)
        if urcs and self.urc_callback:
            self.urc_callback("\n".join(urcs))
        return "\n".join(clean).strip()

    def is_ok(self, resp: str) -> bool:
        return "OK" in resp and "ERROR" not in resp

    # ── Read parameters ───────────────────────────────────────────────

    def read_modem_info(self) -> ModemInfo:
        info = ModemInfo(port=self.port)
        raw = self.send("ATI", 1.0)
        for line in raw.splitlines():
            if "Model:" in line:
                info.model = line.split("Model:")[1].strip()
            elif "Revision:" in line:
                info.firmware = line.split("Revision:")[1].strip()
            elif "IMEI:" in line:
                info.imei = line.split("IMEI:")[1].strip()
        if not info.imei:
            r = self.send("AT+CGSN", 1.0)
            for line in r.splitlines():
                if line.strip().isdigit():
                    info.imei = line.strip()

        r = self.send("AT+CGMR", 1.0)
        if "+CGMR:" in r:
            info.firmware = r.split("+CGMR:")[1].strip()

        r = self.send("AT+CIMI", 1.0)
        for line in r.splitlines():
            if line.strip().isdigit() and len(line.strip()) >= 14:
                info.imsi = line.strip()

        info.iccid = self.send("AT+CCID", 1.0)
        r = self.send("AT+CNUM", 1.0)
        if "+CNUM:" in r:
            info.msisdn = r.split(",")[1].strip().replace('"', '') if "," in r else ""

        return info

    def read_network_info(self) -> NetworkInfo:
        info = NetworkInfo()
        self.send("AT+CEREG=2", 0.3)
        r = self.send("AT+CEREG?", 1.5)
        if "+CEREG:" in r:
            parts = r.split("+CEREG:")[1].split(",")
            stat = int(parts[1].strip()) if len(parts) > 1 else 0
            info.registered = stat in (1, 5)
            info.roaming = stat == 5
            if len(parts) > 3:
                info.tac = parts[2].strip().replace('"', '')
                info.cell_id = parts[3].strip().replace('"', '')

        r = self.send("AT+COPS?", 1.5)
        if "+COPS:" in r and "," in r:
            parts = r.split("+COPS:")[1].split(",")
            if len(parts) > 2:
                info.operator = parts[2].strip().replace('"', '')
            if len(parts) > 3:
                act = parts[3].strip()
                info.technology = {
                    "0": "GSM", "2": "UTRAN", "7": "LTE",
                    "8": "LTE-M", "9": "NB-IoT"
                }.get(act, act)

        r = self.send("AT+CSQ", 1.0)
        if "+CSQ:" in r:
            try:
                val = int(r.split("+CSQ:")[1].split(",")[0].strip())
                info.csq = val
                info.rssi_dbm = -113 + val * 2 if val != 99 else 0
            except ValueError:
                pass

        r = self.send("AT+CPSI?", 1.5)
        if "+CPSI:" in r and "LTE" in r:
            parts = r.split("+CPSI:")[1].split(",")
            if len(parts) >= 14:
                try:
                    info.band     = parts[6].strip()
                    info.earfcn   = parts[7].strip()
                    info.rsrq     = int(parts[10].strip())
                    info.rsrp     = int(parts[11].strip())
                    info.sinr     = int(parts[13].strip())
                except (ValueError, IndexError):
                    pass

        return info

    def read_data_info(self) -> DataInfo:
        info = DataInfo()
        r = self.send("AT+CGDCONT?", 1.5)
        for line in r.splitlines():
            if "+CGDCONT: 1," in line:
                parts = line.split(",")
                if len(parts) >= 3:
                    info.apn_type = parts[1].strip().replace('"', '')
                    info.apn      = parts[2].strip().replace('"', '')

        r = self.send("AT+CGACT?", 1.0)
        for line in r.splitlines():
            if "+CGACT: 1," in line:
                info.active = line.strip().endswith(",1")

        r = self.send("AT+CGPADDR=1", 1.0)
        if "+CGPADDR:" in r:
            parts = r.split("+CGPADDR:")[1].split(",")
            if len(parts) > 1:
                info.ip = parts[1].strip().replace('"', '')

        return info

    def read_sms_info(self) -> SmsInfo:
        info = SmsInfo()
        self.send("AT+CMGF=1", 0.3)
        r = self.send("AT+CSCA?", 1.0)
        if "+CSCA:" in r:
            try:
                raw_smsc = r.split('"')[1]
                info.smsc = raw_smsc
                # detect UTF-16 bug
                if len(raw_smsc) > 10 and all(c in "0123456789ABCDEFabcdef" for c in raw_smsc):
                    decoded = ''.join(
                        chr(int(raw_smsc[i:i+4], 16))
                        for i in range(0, len(raw_smsc), 4)
                    )
                    if decoded.startswith("+"):
                        info.smsc_utf16_bug = True
                        info.smsc_decoded = decoded
            except (IndexError, ValueError):
                pass

        r = self.send("AT+CGSMS?", 1.0)
        if "+CGSMS:" in r:
            try:
                info.bearer = int(r.split("+CGSMS:")[1].strip())
            except ValueError:
                pass

        r = self.send("AT+CPMS?", 1.5)
        if "+CPMS:" in r:
            parts = r.split("+CPMS:")[1].split(",")
            if len(parts) >= 3:
                info.storage = parts[0].strip().replace('"', '')
                try:
                    info.storage_used  = int(parts[1].strip())
                    info.storage_total = int(parts[2].strip())
                except ValueError:
                    pass

        return info

    # ── Write parameters ──────────────────────────────────────────────

    def set_apn(self, apn: str, pdp: int = 1, pdp_type: str = "IP") -> bool:
        self.send(f"AT+CGACT=0,{pdp}", 1.0)
        r = self.send(f'AT+CGDCONT={pdp},"{pdp_type}","{apn}"')
        if not self.is_ok(r):
            return False
        self.send(f"AT+CGACT=1,{pdp}", 3.0)
        return True

    def set_smsc(self, smsc: str) -> bool:
        self.send("AT+CMGF=1", 0.3)
        r = self.send(f'AT+CSCA="{smsc}",145')
        return self.is_ok(r)

    def set_network_mode(self, mode: int) -> bool:
        r = self.send(f"AT+CNMP={mode}")
        return self.is_ok(r)

    def set_sms_storage(self, storage: str = "ME") -> bool:
        r = self.send(f'AT+CPMS="{storage}","{storage}","{storage}"', 3.0)
        return self.is_ok(r)

    def reset_rf(self):
        self.send("AT+CFUN=0", 3.0)
        self.send("AT+CFUN=1", 10.0)

    def factory_reset(self):
        self.send("AT&F")
        self.send("ATZ")

    # ── SMS send (PDU with embedded SMSC — bypasses UTF-16 bug) ───────

    def send_sms(self, destination: str, message: str, smsc: str) -> bool:
        """Send SMS via PDU with SMSC embedded. Bypasses AT+CSCA bug."""

        def enc_smsc(n):
            d = n.lstrip("+")
            if len(d) % 2: d += "F"
            b = bytes(int(d[i+1], 16) << 4 | int(d[i], 16) for i in range(0, len(d), 2))
            return bytes([len(b) + 1, 0x91]) + b

        def enc_da(n):
            r = n.lstrip("+"); l = len(r)
            if len(r) % 2: r += "F"
            b = bytes(int(r[i+1], 16) << 4 | int(r[i], 16) for i in range(0, len(r), 2))
            return bytes([l, 0x91]) + b

        def gsm7(t):
            G = '@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ !"#¤%&\'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ`¿abcdefghijklmnopqrstuvwxyzäöñüà'
            s = [G.index(c) if c in G else 63 for c in t]
            b = ''.join(f'{x:07b}'[::-1] for x in s)
            b += '0' * ((8 - len(b) % 8) % 8)
            return bytes(int(b[i:i+8][::-1], 2) for i in range(0, len(b), 8))

        self.send("AT+CMGF=0", 0.3)
        tpdu = bytes([0x11, 0x00]) + enc_da(destination) + bytes([0x00, 0x00, 0xFF, len(message)]) + gsm7(message)
        pdu  = enc_smsc(smsc) + tpdu
        ph   = pdu.hex().upper()

        with self._lock:
            self._ser.reset_input_buffer()
            self._ser.write(f"AT+CMGS={len(tpdu)}\r\n".encode())
            time.sleep(1.5)
            prompt = self._ser.read_all().decode(errors="replace")
            if ">" not in prompt:
                return False
            self._ser.write((ph + "\x1a").encode())
            time.sleep(6.0)
            resp = self._ser.read_all().decode(errors="replace")
            return "+CMGS:" in resp
