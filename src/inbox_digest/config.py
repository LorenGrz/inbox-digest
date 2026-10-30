"""Constantes de configuración. La lectura de env vars y secretos llega en la fase 3.

Regla dura del proyecto: ninguna API key vive en el repo ni en el código. Acá
solo hay valores que no son secretos y que la lógica pura necesita conocer.
"""

from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")

# Cuántos días hacia adelante mira el digest.
LOOKAHEAD_DAYS = 14

# Etiqueta donde cae todo lo que no es importante.
LATER_LABEL = "Revisar después"

# Etiqueta que el usuario le pone a un mail para decir "esto no era importante".
# Reemplaza al botón de la web app del original: Gmail no deja meter formularios
# en un mail, y una etiqueta se puede poner desde el celular.
FEEDBACK_LABEL = "No importante"

# Modelo de Gemini por defecto. Flash alcanza y entra en el tier gratuito.
#
# Ojo con los 2.5: Google limita el acceso a cuentas que ya los venían usando,
# así que una API key nueva recibe 404. Por eso el default es un 3.x y se puede
# pisar por env var sin tocar el código.
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"
