"""
Bot de monitoreo de asientos - Showcase Norcenter IMAX
--------------------------------------------------------
Versión para GitHub Actions: hace UNA sola pasada (revisa, notifica si
corresponde, termina). El scheduler es el cron del workflow, no un loop
interno.

Qué hace:
  1. Abre la página de venta de entradas de Showcase (voyalcine.net).
  2. Selecciona el cine (IMAX Theatre Norcenter) y la película que definas.
  3. Para cada función disponible, entra a la selección de asientos.
  4. Revisa si alguno de tus asientos preferidos está libre.
  5. Si encuentra disponibilidad NUEVA, te manda un mail con el detalle y
     el link para completar la compra vos mismo. El bot NUNCA hace el
     checkout ni toca datos de pago.
  6. Si algo se rompe (ej: el sitio cambió y ya no encuentra los
     elementos esperados), te manda un mail de ALERTA DE FALLO distinto,
     para que sepas que el bot dejó de funcionar y no lo confundas con
     "no hay asientos".

IMPORTANTE - Antes de correrlo tenés que completar 4 selectores (buscá
"# TODO" en este archivo). Instrucciones en COMO_COMPLETAR_LOS_SELECTORES
más abajo.

Credenciales: se leen de variables de entorno (en GitHub Actions vienen
de Secrets, nunca quedan escritas en el código):
  EMAIL_FROM, EMAIL_APP_PASSWORD, EMAIL_TO

COMO_COMPLETAR_LOS_SELECTORES:
  1. Abrí https://www.voyalcine.net/showcase/boleteria.aspx en Chrome.
  2. F12 → pestaña "Elements" → ícono de inspeccionar (flecha) → click
     sobre el dropdown "Seleccione Cine...". Copiá el id del <select> →
     SELECTOR_CINE.
  3. Elegí "IMAX Theatre (Norcenter)", esperá el dropdown de película,
     inspeccionalo → SELECTOR_PELICULA.
  4. Elegí la película, esperá el dropdown/lista de horarios → SELECTOR_HORARIO.
  5. Elegí un horario, esperá el mapa de butacas. Inspeccioná una butaca
     LIBRE. Anotá el patrón de clase CSS → SEAT_FREE_CLASS, y cómo indica
     fila/número → SEAT_LABEL_ATTR.
"""

import json
import os
import re
import smtplib
import ssl
import sys
from dataclasses import dataclass, field
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ============================================================
# CONFIGURACIÓN - editá esta sección
# ============================================================

URL_BOLETERIA = "https://www.voyalcine.net/showcase/boleteria.aspx"

CINE_TEXTO = "IMAX Theatre (Norcenter)"
PELICULA_TEXTO = "NOMBRE DE LA PELICULA"    # substring del título que buscás

FILAS_PREFERIDAS = ["I", "H", "J"]
BUTACAS_PREFERIDAS = range(17, 21)  # 17,18,19,20

# --- Selectores del sitio (COMPLETAR - ver COMO_COMPLETAR_LOS_SELECTORES) ---
SELECTOR_CINE = "select#TODO_id_del_select_de_cine"
SELECTOR_PELICULA = "select#TODO_id_del_select_de_pelicula"
SELECTOR_HORARIO = "#TODO_selector_de_horarios"

SEAT_FREE_CLASS = ".asiento.libre"     # TODO: ajustar
SEAT_LABEL_ATTR = "data-seat"          # TODO: ajustar (o None si el label
                                        # está en el texto visible)

# --- Email (se leen de variables de entorno / GitHub Secrets) ---
EMAIL_FROM = os.environ.get("EMAIL_FROM")
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD")
EMAIL_TO = os.environ.get("EMAIL_TO", EMAIL_FROM)
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465

STATE_FILE = Path(__file__).parent / "notified_state.json"

# ============================================================
# LÓGICA
# ============================================================


@dataclass
class Funcion:
    horario_label: str
    asientos_libres_preferidos: list = field(default_factory=list)


def cargar_estado() -> set:
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text()))
    return set()


def guardar_estado(estado: set):
    STATE_FILE.write_text(json.dumps(sorted(estado)))


def parsear_fila_butaca(label: str):
    m = re.match(r"([A-Za-z]+)\s*-?\s*(\d+)", label.strip())
    if not m:
        return None, None
    return m.group(1).upper(), int(m.group(2))


def es_preferido(fila: str, butaca: int) -> bool:
    return fila in FILAS_PREFERIDAS and butaca in BUTACAS_PREFERIDAS


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


def enviar_mail_disponibilidad(funcion: Funcion):
    asientos_str = ", ".join(funcion.asientos_libres_preferidos)
    cuerpo = f"""¡Se liberaron asientos preferidos!

Película: {PELICULA_TEXTO}
Cine: {CINE_TEXTO}
Función: {funcion.horario_label}
Asientos preferidos libres: {asientos_str}

Entrá a completar la compra vos mismo (el bot no compra por vos):
{URL_BOLETERIA}

Ojo: la disponibilidad puede cambiar en cualquier momento, andá rápido.
"""
    _enviar_mail(f"🎬 Asientos disponibles: {PELICULA_TEXTO} - {funcion.horario_label}", cuerpo)
    print(f"[{datetime.now()}] Mail de disponibilidad enviado: {funcion.horario_label}")


def enviar_mail_alerta_fallo(error: Exception):
    cuerpo = f"""El bot de monitoreo de entradas encontró un error y no pudo
completar la revisión. Puede ser que el sitio cambió su estructura y hay
que actualizar los selectores del script.

Error:
{repr(error)}

Revisá el workflow en GitHub Actions para más detalle (logs completos).
"""
    _enviar_mail("⚠️ El bot de entradas se rompió - revisar", cuerpo)
    print(f"[{datetime.now()}] Mail de alerta de fallo enviado.")


def revisar_funcion(page, horario_label: str) -> Funcion:
    funcion = Funcion(horario_label=horario_label)

    asientos_libres = page.query_selector_all(SEAT_FREE_CLASS)
    for asiento in asientos_libres:
        if SEAT_LABEL_ATTR:
            label = asiento.get_attribute(SEAT_LABEL_ATTR) or ""
        else:
            label = asiento.inner_text()

        fila, butaca = parsear_fila_butaca(label)
        if fila and butaca and es_preferido(fila, butaca):
            funcion.asientos_libres_preferidos.append(f"{fila}{butaca}")

    return funcion


def ciclo_de_revision(page, estado_notificado: set):
    page.goto(URL_BOLETERIA, wait_until="networkidle")

    page.select_option(SELECTOR_CINE, label=CINE_TEXTO)
    page.wait_for_timeout(1500)

    page.select_option(SELECTOR_PELICULA, label=re.compile(PELICULA_TEXTO, re.I))
    page.wait_for_timeout(1500)

    horarios = page.query_selector_all(f"{SELECTOR_HORARIO} option")
    horario_labels = [h.inner_text() for h in horarios if h.inner_text().strip()]

    if not horario_labels:
        raise RuntimeError(
            "No se encontraron horarios. Es probable que un selector "
            "(SELECTOR_CINE, SELECTOR_PELICULA o SELECTOR_HORARIO) ya no "
            "coincida con el HTML real del sitio."
        )

    for horario_label in horario_labels:
        try:
            page.select_option(SELECTOR_HORARIO, label=horario_label)
            page.wait_for_timeout(1500)

            funcion = revisar_funcion(page, horario_label)

            if funcion.asientos_libres_preferidos:
                clave = f"{PELICULA_TEXTO}|{horario_label}|{','.join(sorted(funcion.asientos_libres_preferidos))}"
                if clave not in estado_notificado:
                    enviar_mail_disponibilidad(funcion)
                    estado_notificado.add(clave)
                else:
                    print(f"[{datetime.now()}] Ya notificado: {horario_label}")
            else:
                print(f"[{datetime.now()}] Sin asientos preferidos libres: {horario_label}")

        except PWTimeout:
            print(f"[{datetime.now()}] Timeout revisando {horario_label}, sigo con la próxima")
            continue


def main():
    estado_notificado = cargar_estado()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            ciclo_de_revision(page, estado_notificado)
            browser.close()

        guardar_estado(estado_notificado)
        print(f"[{datetime.now()}] Revisión completada OK.")

    except Exception as e:
        print(f"[{datetime.now()}] ERROR: {e}")
        enviar_mail_alerta_fallo(e)
        sys.exit(1)  # marca el run de GitHub Actions como fallido


if __name__ == "__main__":
    main()
