"""
Guided diagnostic sequence — runs all checks and returns a structured report.
Identifies known issues (SMSC UTF-16 bug, no registration, etc.)
"""

from dataclasses import dataclass, field
from typing import List
from core.modem import Modem, ModemInfo, NetworkInfo, DataInfo, SmsInfo


SEVERITY_OK      = "ok"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR   = "error"


@dataclass
class DiagnosticIssue:
    severity: str        # ok | warning | error
    code: str            # machine-readable code
    title: str
    description: str
    fix: str = ""


@dataclass
class DiagnosticReport:
    modem: ModemInfo       = field(default_factory=ModemInfo)
    network: NetworkInfo   = field(default_factory=NetworkInfo)
    data: DataInfo         = field(default_factory=DataInfo)
    sms: SmsInfo           = field(default_factory=SmsInfo)
    issues: List[DiagnosticIssue] = field(default_factory=list)
    log: List[str]         = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(i.severity == SEVERITY_ERROR for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == SEVERITY_WARNING for i in self.issues)


def run(modem: Modem, progress_cb=None) -> DiagnosticReport:
    """
    Run full diagnostic sequence.
    progress_cb(step: int, total: int, label: str) called at each step.
    """
    report = DiagnosticReport()
    steps = [
        ("Lendo informações do módulo",  _check_modem),
        ("Verificando SIM",              _check_sim),
        ("Verificando registro na rede", _check_network),
        ("Verificando dados / APN",      _check_data),
        ("Verificando stack SMS",        _check_sms),
    ]
    total = len(steps)
    for i, (label, fn) in enumerate(steps):
        if progress_cb:
            progress_cb(i + 1, total, label)
        fn(modem, report)

    return report


# ── Check functions ───────────────────────────────────────────────────────────

def _check_modem(modem: Modem, report: DiagnosticReport):
    report.log.append("Lendo identificação do módulo...")
    report.modem = modem.read_modem_info()
    if not report.modem.imei:
        report.issues.append(DiagnosticIssue(
            severity=SEVERITY_ERROR,
            code="NO_IMEI",
            title="IMEI não encontrado",
            description="Não foi possível ler o IMEI do módulo.",
            fix="Verifique a conexão USB e tente novamente."
        ))
    else:
        report.log.append(f"  Módulo: {report.modem.model} | IMEI: {report.modem.imei}")


def _check_sim(modem: Modem, report: DiagnosticReport):
    report.log.append("Verificando SIM...")
    r = modem.send("AT+CPIN?", 1.5)
    if "READY" in r:
        report.log.append("  SIM: READY")
    elif "SIM PIN" in r:
        report.issues.append(DiagnosticIssue(
            severity=SEVERITY_ERROR,
            code="SIM_PIN_LOCKED",
            title="SIM bloqueado por PIN",
            description="O SIM requer PIN para desbloquear.",
            fix="Desbloqueie o PIN com AT+CPIN=<pin>."
        ))
    elif "ERROR" in r or "not inserted" in r.lower():
        report.issues.append(DiagnosticIssue(
            severity=SEVERITY_ERROR,
            code="SIM_NOT_INSERTED",
            title="SIM não detectado",
            description="Nenhum SIM encontrado no slot.",
            fix="Verifique se o SIM está corretamente inserido."
        ))

    if report.modem.imsi:
        mcc = report.modem.imsi[:3]
        mnc = report.modem.imsi[3:5]
        report.log.append(f"  IMSI: {report.modem.imsi} (MCC={mcc} MNC={mnc})")


def _check_network(modem: Modem, report: DiagnosticReport):
    report.log.append("Verificando registro na rede...")
    report.network = modem.read_network_info()
    if report.network.registered:
        status = "roaming" if report.network.roaming else "home"
        report.log.append(f"  Rede: registrado ({status}) — {report.network.operator} {report.network.technology}")
        report.log.append(f"  Sinal: CSQ={report.network.csq} ({report.network.rssi_dbm} dBm)")
        if report.network.rssi_dbm < -100 and report.network.rssi_dbm != 0:
            report.issues.append(DiagnosticIssue(
                severity=SEVERITY_WARNING,
                code="WEAK_SIGNAL",
                title="Sinal fraco",
                description=f"RSSI = {report.network.rssi_dbm} dBm (limite recomendado: -100 dBm).",
                fix="Mova o rastreador para área com melhor cobertura."
            ))
    else:
        r = modem.send("AT+CEREG?", 1.0)
        stat = 0
        if "+CEREG:" in r:
            try:
                stat = int(r.split("+CEREG:")[1].split(",")[1].strip())
            except (IndexError, ValueError):
                pass
        desc = {3: "Registro negado — SIM bloqueado ou plano vencido."}.get(
            stat, "Sem registro na rede.")
        report.issues.append(DiagnosticIssue(
            severity=SEVERITY_ERROR,
            code="NOT_REGISTERED",
            title="Sem registro na rede",
            description=desc,
            fix="Verifique o SIM, cobertura e configuração da operadora."
        ))


def _check_data(modem: Modem, report: DiagnosticReport):
    report.log.append("Verificando dados...")
    report.data = modem.read_data_info()
    if report.data.active:
        report.log.append(f"  Dados: ativos — APN={report.data.apn} IP={report.data.ip}")
    else:
        report.issues.append(DiagnosticIssue(
            severity=SEVERITY_WARNING,
            code="DATA_INACTIVE",
            title="Dados inativos",
            description=f"PDP context inativo. APN configurado: '{report.data.apn}'.",
            fix="Configure o APN correto da operadora e ative o contexto."
        ))


def _check_sms(modem: Modem, report: DiagnosticReport):
    report.log.append("Verificando SMS...")
    report.sms = modem.read_sms_info()

    if report.sms.smsc_utf16_bug:
        report.issues.append(DiagnosticIssue(
            severity=SEVERITY_ERROR,
            code="SMSC_UTF16_BUG",
            title="Bug de firmware: SMSC em UTF-16",
            description=(
                f"O SMSC está armazenado em UTF-16 hexadecimal "
                f"('{report.sms.smsc}'). "
                f"Valor decodificado: {report.sms.smsc_decoded}. "
                f"Firmware afetado: LSOFTSIM. "
                f"Envio de SMS pelo método padrão falha com CMS ERROR 302/151."
            ),
            fix=(
                "Use envio via PDU com SMSC embutido (função send_sms do módulo modem.py). "
                "Para correção definitiva, solicite atualização de firmware ao fabricante."
            )
        ))
        report.log.append(f"  !! SMSC UTF-16 detectado → {report.sms.smsc_decoded}")
    else:
        report.log.append(f"  SMSC: {report.sms.smsc}")

    if report.sms.storage_total > 0:
        report.log.append(
            f"  Storage: {report.sms.storage} {report.sms.storage_used}/{report.sms.storage_total}"
        )
        if report.sms.storage_total < 10:
            report.issues.append(DiagnosticIssue(
                severity=SEVERITY_WARNING,
                code="SMS_STORAGE_LIMITED",
                title="Storage SMS limitado",
                description=f"SIM tem apenas {report.sms.storage_total} slots de SMS.",
                fix="Use AT+CPMS='ME','ME','ME' para usar memória interna (180 slots)."
            ))
