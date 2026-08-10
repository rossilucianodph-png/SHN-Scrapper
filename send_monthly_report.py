#!/usr/bin/env python3
"""
Generador y envío automático del resumen mensual de Puerto Belgrano por email.

Comportamiento (según la fecha actual en hora de Argentina, UTC-3):
  - Día 15:  envía resumen PARCIAL con los datos del mes en curso (día 1 al 15).
  - Día 1:   envía resumen MENSUAL con los datos del mes anterior completo.
  - Otro día: no envía nada.

La planilla se genera en formato .xls (HTML con tabla coloreada, igual a la
exportación de la página web) y se adjunta al correo.

Configuración (variables de entorno):
  SMTP_USER   -> dirección de Gmail que envía (necesita App Password)
  SMTP_PASS   -> contraseña de aplicación de Gmail
  DEST_EMAIL  -> destinatario (por defecto rsciarrone@gmail.com)

Uso:
  python send_monthly_report.py
  python send_monthly_report.py --date 2026-07-15            # simula esa fecha
  python send_monthly_report.py --date 2026-07-15 --no-send  # genera sin enviar
"""

import argparse
import os
import smtplib
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from generate_summary import (
    HOUR_END,
    HOUR_START,
    analyze_days,
    badge_colors,
    cell_colors,
    filter_hours,
    load_all_csvs,
)

# Argentina está en UTC-3 sin horario de verano.
ARG_TZ = timezone(timedelta(hours=-3))

DEST_EMAIL = os.environ.get("DEST_EMAIL", "rsciarrone@gmail.com")
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

MESES_ES = [
    "",
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def _periodo_hoy(today):
    """Determina el período a reportar según el día de hoy.

    Retorna (tipo, inicio, fin, texto_periodo) o None si hoy no corresponde.
    """
    if today.day == 15:
        inicio = today.replace(day=1)
        fin = today
        texto = f"{inicio.strftime('%d/%m/%Y')} al {fin.strftime('%d/%m/%Y')} (parcial)"
        return "parcial", inicio.replace(tzinfo=None), fin.replace(tzinfo=None), texto

    if today.day == 1:
        fin = today.replace(day=1) - timedelta(days=1)  # último día del mes anterior
        inicio = fin.replace(day=1)
        texto = f"{inicio.strftime('%d/%m/%Y')} al {fin.strftime('%d/%m/%Y')} (mensual)"
        return "mensual", inicio.replace(tzinfo=None), fin.replace(tzinfo=None), texto

    return None


def cargar_datos(inicio, fin):
    """Carga los CSVs y retorna los resultados diarios dentro del período."""
    df = load_all_csvs()
    if df.empty:
        return []

    mask = (df["fecha"] >= inicio) & (df["fecha"] <= fin.replace(hour=23, minute=59, second=59))
    df = df[mask]
    if df.empty:
        return []

    df = filter_hours(df)
    return analyze_days(df)


def build_xls_html(day_results):
    """Construye la planilla .xls (HTML con tabla) con colores y bordes."""
    hours_range = list(range(HOUR_START, HOUR_END + 1))

    headers = ["<th style=\"border:1px solid #000000;background:#2d3748;color:#ffffff;\">Fecha</th>"]
    headers += [
        f"<th style=\"border:1px solid #000000;background:#2d3748;color:#ffffff;\">{h:02d}:00</th>"
        for h in hours_range
    ]
    headers.append("<th style=\"border:1px solid #000000;background:#2d3748;color:#ffffff;\">Rango Alerta</th>")

    rows = []
    for day in day_results:
        cells = [f"<td style=\"border:1px solid #000000;\">{day['display']}</td>"]
        for h in hours_range:
            info = day["hours"].get(h)
            if info and info["valor"] is not None:
                bg = cell_colors(info["valor"])
                cells.append(f"<td style=\"border:1px solid #000000;background:{bg};\">{info['valor']:.2f}</td>")
            else:
                cells.append("<td style=\"border:1px solid #000000;color:#9ca3af;\">S/D</td>")
        if day["tiene_alerta"]:
            bg = badge_colors(day["horas_alerta"])
            cells.append(f"<td style=\"border:1px solid #000000;background:{bg};\">{day['alerta_inicio']} - {day['alerta_fin']}</td>")
        else:
            cells.append("<td style=\"border:1px solid #000000;\">-</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")

    html = (
        "<html xmlns:o=\"urn:schemas-microsoft-com:office:office\" "
        "xmlns:x=\"urn:schemas-microsoft-com:office:excel\">"
        "<head><meta charset=\"utf-8\"></head><body>"
        "<table style=\"border-collapse:collapse;\">"
        "<thead><tr>" + "".join(headers) + "</tr></thead>"
        "<tbody>" + "\n".join(rows) + "</tbody>"
        "</table></body></html>"
    )
    return html


def enviar_email(archivo, asunto, cuerpo, smtp_user, smtp_pass):
    """Envía el correo con la planilla adjunta por SMTP de Gmail."""
    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = DEST_EMAIL
    msg["Subject"] = asunto
    msg.attach(MIMEText(cuerpo, "plain", "utf-8"))

    nombre = os.path.basename(archivo)
    with open(archivo, "rb") as f:
        part = MIMEBase("application", "vnd.ms-excel")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", "attachment", filename=("utf-8", "", nombre))
    msg.attach(part)

    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=60)
    try:
        server.ehlo()
        if server.has_extn("starttls"):
            server.starttls()
            server.ehlo()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [DEST_EMAIL], msg.as_string())
    finally:
        server.quit()


def main():
    parser = argparse.ArgumentParser(description="Envía el resumen mensual de Puerto Belgrano.")
    parser.add_argument("--date", help="Simula que hoy es esta fecha (YYYY-MM-DD).")
    parser.add_argument("--no-send", action="store_true", help="Genera la planilla pero no envía el correo.")
    args = parser.parse_args()

    if args.date:
        today = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=ARG_TZ)
        print(f"[Simulación] Fecha forzada: {today.strftime('%d/%m/%Y')}")
    else:
        today = datetime.now(ARG_TZ)
        print(f"Fecha actual (Argentina): {today.strftime('%d/%m/%Y %H:%M')}")

    periodo = _periodo_hoy(today)
    if periodo is None:
        print(f"Hoy es día {today.day}: no corresponde enviar resumen (solo días 1 y 15).")
        return

    tipo, inicio, fin, texto_periodo = periodo
    mes_num = inicio.month
    anio = inicio.year
    nombre_mes = MESES_ES[mes_num]
    print(f"Período a reportar: {texto_periodo}")

    day_results = cargar_datos(inicio, fin)
    if not day_results:
        print("[Advertencia] No hay datos de mareas en el período. No se envía nada.")
        return

    total = len(day_results)
    alertas = sum(1 for d in day_results if d["tiene_alerta"])
    normales = total - alertas
    print(f"Días con datos: {total} | Con alerta (>3.50m): {alertas} | Sin alerta: {normales}")

    # Planilla .xls (formato HTML de Excel, con BOM UTF-8)
    xls_html = build_xls_html(day_results)
    sufijo = "parcial" if tipo == "parcial" else "mensual"
    nombre_archivo = f"Resumen_Puerto_Belgrano_{nombre_mes}_{anio}_{sufijo}.xls"
    ruta_archivo = os.path.join(tempfile.gettempdir(), nombre_archivo)
    with open(ruta_archivo, "w", encoding="utf-8-sig") as f:
        f.write(xls_html)
    print(f"[OK] Planilla generada: {ruta_archivo}")

    asunto = f"Resumen {'parcial' if tipo == 'parcial' else 'mensual'} - Puerto Belgrano - {nombre_mes} {anio}"
    cuerpo = (
        "Hola,\n\n"
        f"Te adjunto el resumen de niveles del Puerto Belgrano para el período "
        f"{inicio.strftime('%d/%m/%Y')} al {fin.strftime('%d/%m/%Y')}.\n\n"
        f"- Días con datos: {total}\n"
        f"- Días con alerta (>3.50m): {alertas}\n"
        f"- Días sin alerta: {normales}\n\n"
        "Saludos,\nSistema automático de monitoreo SHN."
    )

    if args.no_send:
        print("[Modo prueba] No se envía el correo (--no-send).")
        print(f"Asunto: {asunto}")
        print(f"Destinatario: {DEST_EMAIL}")
        return

    smtp_user = os.environ.get("SMTP_USER", "").strip()
    smtp_pass = os.environ.get("SMTP_PASS", "").strip()
    if not smtp_user or not smtp_pass:
        print("[Error] Faltan las variables SMTP_USER y/o SMTP_PASS para enviar el correo.")
        sys.exit(1)

    print(f"Enviando a {DEST_EMAIL}...")
    try:
        enviar_email(ruta_archivo, asunto, cuerpo, smtp_user, smtp_pass)
    except Exception as e:
        print(f"[Error] No se pudo enviar el correo: {e}")
        sys.exit(1)

    print("[Éxito] Correo enviado.")


if __name__ == "__main__":
    main()
