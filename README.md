# Bot de aviso de asientos - Showcase Norcenter IMAX

Chequea cada 10 minutos si tus asientos preferidos (filas I/H/J, butacas
17-20) están libres para la función que definas, y te avisa por mail.
El bot **no compra entradas** — vos hacés el checkout siempre.

## Setup (una sola vez)

1. **Creá un repo en GitHub** (puede ser público o privado) y subí estos
   archivos tal cual están.

2. **Completá los selectores en `monitor.py`** (buscá `# TODO`).
   Instrucciones detalladas en el comentario `COMO_COMPLETAR_LOS_SELECTORES`
   arriba del archivo. Necesitás inspeccionar la página real con F12.

3. **Editá `PELICULA_TEXTO`** en `monitor.py` con el nombre (o parte del
   nombre) de la película que querés monitorear.

4. **Generá una contraseña de aplicación de Gmail:**
   - Activá verificación en 2 pasos: https://myaccount.google.com/security
   - Generá la clave acá: https://myaccount.google.com/apppasswords

5. **Cargá los Secrets en GitHub:**
   - En tu repo → Settings → Secrets and variables → Actions → "New repository secret"
   - Creá estos 3:
     - `EMAIL_FROM` → tu mail de Gmail
     - `EMAIL_APP_PASSWORD` → la contraseña de aplicación generada en el paso 4
     - `EMAIL_TO` → a dónde querés que llegue el aviso (puede ser el mismo mail)

6. **Listo.** El workflow (`.github/workflows/check-seats.yml`) corre solo
   cada 10 minutos. Podés probarlo manualmente desde la pestaña **Actions**
   del repo → "Chequear asientos disponibles" → "Run workflow".

## Si el bot deja de avisar

Revisá la pestaña **Actions** en GitHub. Si un run aparece en rojo (❌),
también te va a llegar un mail de alerta distinto ("El bot de entradas se
rompió"). Lo más probable es que el sitio cambió su HTML y hay que
reajustar los selectores de `monitor.py`.

## Cambiar el intervalo

En `check-seats.yml`, la línea `cron: "*/10 * * * *"` — cambiá el `10` por
los minutos que quieras (mínimo recomendado: 5, para no generar tráfico
excesivo al sitio).
