# Bot de aviso - nuevas funciones de La Odisea (IMAX Norcenter)

Avisa por mail apenas el cine publique funciones para el **6 de agosto
de 2026 en adelante** (hoy sólo hay cargado hasta el 5/8). No hace
login, no reserva entradas, no toca el mapa de asientos — sólo lee el
selector público de "Día" de la boletería y compara contra la fecha de
corte.

## Setup

1. **Generá una contraseña de aplicación de Gmail:**
   - Activá verificación en 2 pasos: https://myaccount.google.com/security
   - Generá la clave: https://myaccount.google.com/apppasswords

2. **Cargá los Secrets en GitHub** (repo → Settings → Secrets and
   variables → Actions → New repository secret):
   - `EMAIL_FROM` → tu mail de Gmail
   - `EMAIL_APP_PASSWORD` → la contraseña de aplicación del paso 1
   - `EMAIL_TO` → a dónde querés que llegue el aviso

3. **Probalo manual** desde la pestaña Actions → "Chequear nuevas
   funciones de La Odisea" → "Run workflow".

## Qué pasa cuando te avisa

El bot NO reserva ni compra nada. Cuando te llega el mail, entrás vos a
mano a:
https://www.voyalcine.net/showcase/boleteria.aspx
elegís La Odisea → IMAX → la fecha nueva → horario (19:00 o 22:35) →
y ahí sí, si querés, seguimos armando la parte de chequeo de asientos
preferidos (filas H/I/J, butacas 17-20) para esa función puntual, una
vez que exista de verdad (esa parte sí requiere login con tu cuenta,
así que la dejamos aparte para no correr ese riesgo mientras no hace
falta).

## Cambiar la fecha de corte

En `monitor.py`, la línea `FECHA_CORTE = date(2026, 8, 6)` — cambiala
si querés otro punto de corte.

## Si el bot deja de avisar

Revisá la pestaña Actions en GitHub. Si un run aparece en rojo (❌),
también te llega un mail de alerta aparte. La causa más probable es que
"La Odisea" salió de cartelera en ese cine.
