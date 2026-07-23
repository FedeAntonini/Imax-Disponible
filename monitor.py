"""
Bot de aviso: nuevas funciones de "La Odisea" (IMAX Norcenter)
------------------------------------------------------------------
Objetivo: avisarte apenas el cine publique funciones para el 6 de
agosto de 2026 en adelante (hoy sólo hay cargado hasta el 5/8).

IMPORTANTE - esta versión es mucho más liviana que la anterior:
  - NO hace falta login (el dropdown de días es público).
  - NO reserva ninguna entrada ni toca el mapa de asientos.
  - Sólo lee las opciones del selector de "Día" para Cine=IMAX Norcenter
    y Película=La Odisea, y compara contra la fecha de corte.

Por ser una consulta liviana (nada de reservas ni login), se puede
correr con un intervalo corto sin preocuparse por el riesgo de la
cuenta.

Una vez que aparezcan fechas nuevas, el mail avisa para que entres vos
a elegir horario (19:00 o 22:35) y completar la compra. Si más adelante
querés que el bot también chequee la disponibilidad de asientos
preferidos (filas H/I/J, 17-20) para esas nuevas funciones, se puede
retomar el bot anterior (el que sí requiere login) una vez que existan
funciones reales para reservar.
"""

import json
import os
import re
import smtplib
import ssl
import sys
from datetime import date
from email.mime.text import MIMEText
from pathlib import Path

from playwright.sync_api import sync_playwright

# ============================================================
# CONFIGURACIÓN
# ============================================================

URL_BOLETERIA = "https://www.voyalcine.net/showcase/boleteria.aspx"

CINE_TEXTO = "IMAX Theatre (Norcenter)"
PELICULA_TEXTO = "La Odisea"

# Fecha de corte: avisar apenas aparezca un día >= a esta fecha.
FECHA_CORTE = date(2026, 8, 6)

# --- Selectores reales del sitio (verificados) ---
SEL_CINE = "select#ctl00_Contenido_lstCinemaFull"
SEL_PELICULA = "select#ctl00_Contenido_lstMovies"
SEL_FORMATO = "select#ctl00_Contenido_lstFormat"
SEL_DIA = "select#ctl00_Contenido_lstDays"

# --- Email (variables de entorno / GitHub Secrets) ---
EMAIL_FROM = os.environ.get("EMAIL_FROM")
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD")
EMAIL_TO = os.environ.get("EMAIL_TO", EMAIL_FROM)
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465

STATE_FILE = Path(__file__).parent / "notified_state.json"

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

# ============================================================
# LÓGICA
# ============================================================


def parsear_fecha(texto: str) -> date | None:
    """Convierte 'miércoles, 6 de agosto de 2026' en date(2026, 8, 6)."""
    m = re.search(r"(\d{1,2})\s+de\s+([a-zA-Zá-ú]+)\s+de\s+(\d{4})", texto, re.I)
    if not m:
        return None
    dia, mes_nombre, anio = m.group(1), m.group(2).lower(), m.group(3)
    mes = MESES.get(mes_nombre)
    if not mes:
        return None
    return date(int(anio), mes, int(dia))


def cargar_estado() -> set:
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text()))
    return set()


def guardar_estado(estado: set):
    STATE_FILE.write_text(json.dumps(sorted(estado)))


def _enviar_mail(asunto: str, cuerpo: str):
    if not EMAIL_FROM or not EMAIL_APP_PASSWORD:
        print("Faltan EMAIL_FROM / EMAIL_APP_PASSWORD en variables de entorno.")
        return
    msg = MIMEText(cuerpo, "plain", "utf-8")
    msg["Subject"] = asunto
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as server:
        server.login(EMAIL_FROM, EMAIL_APP_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())


def enviar_mail_nuevas_fechas(fechas_nuevas: list):
    fechas_str = "\n".join(f"  - {f}" for f in fechas_nuevas)
    cuerpo = f"""¡Salieron funciones nuevas de {PELICULA_TEXTO}!

Cine: {CINE_TEXTO}
Nuevas fechas publicadas:
{fechas_str}

Entrá ya a elegir horario (19:00 o 22:35) y asiento antes de que se agote:
{URL_BOLETERIA}
"""
    _enviar_mail(f"🎬 Nuevas funciones de {PELICULA_TEXTO} disponibles", cuerpo)
    print(f"Mail enviado. Fechas nuevas: {fechas_nuevas}")


def enviar_mail_alerta_fallo(error: Exception):
    cuerpo = f"""El bot de aviso de nuevas funciones encontró un error.

Error:
{repr(error)}

Puede ser que cambió el HTML del sitio, o que la película salió de
cartelera. Revisá el workflow en GitHub Actions para más detalle.
"""
    _enviar_mail("⚠️ El bot de nuevas funciones se rompió - revisar", cuerpo)


def buscar_fechas_disponibles(page) -> list:
    page.goto(URL_BOLETERIA, wait_until="networkidle")

    page.select_option(SEL_CINE, label=CINE_TEXTO)
    page.wait_for_timeout(1500)

    page.select_option(SEL_PELICULA, label=re.compile(re.escape(PELICULA_TEXTO), re.I))
    page.wait_for_timeout(1500)

    page.select_option(SEL_FORMATO, index=1)
    page.wait_for_timeout(1500)

    opciones = page.query_selector_all(f"{SEL_DIA} option")
    textos = [o.inner_text() for o in opciones if o.inner_text().strip()]

    if not textos:
        raise RuntimeError(
            "No se encontró ninguna fecha en el selector de día. Es "
            "posible que 'La Odisea' haya salido de cartelera en este "
            "cine, o que cambiaron los selectores del sitio."
        )

    return textos


def main():
    estado_notificado = cargar_estado()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            textos_fecha = buscar_fechas_disponibles(page)
            browser.close()

        fechas_nuevas = []
        for texto in textos_fecha:
            fecha = parsear_fecha(texto)
            if fecha and fecha >= FECHA_CORTE and texto not in estado_notificado:
                fechas_nuevas.append(texto)

        if fechas_nuevas:
            enviar_mail_nuevas_fechas(fechas_nuevas)
            estado_notificado.update(fechas_nuevas)
        else:
            print("Todavía no hay fechas nuevas (>= 6 de agosto).")

        guardar_estado(estado_notificado)
        print("Revisión completada OK.")

    except Exception as e:
        print(f"ERROR: {e}")
        enviar_mail_alerta_fallo(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
