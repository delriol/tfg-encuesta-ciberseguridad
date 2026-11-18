"""Estado de la encuesta según la configuración y la hora actual.

La encuesta pasa por tres estados:

- prueba: todavía no se publicó. Funciona igual que la versión real, pero las
  respuestas que se carguen se borran al publicarla (sirve para probarla).
- abierta: publicada y recibiendo respuestas.
- cerrada: llegó la fecha de cierre o el investigador la pausó desde el panel.
"""
from datetime import datetime, timezone

from . import db
from .models import Configuracion

PRUEBA = "prueba"
ABIERTA = "abierta"
CERRADA = "cerrada"


def _utc(dt):
    """Devuelve la fecha con zona horaria UTC (SQLite la guarda sin zona horaria)."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def configuracion():
    """Devuelve la única fila de la tabla de configuración (id = 1)."""
    return db.session.get(Configuracion, 1)


def estado_encuesta(ahora=None):
    """Indica si la encuesta está en prueba, abierta o cerrada.

    ahora: momento a evaluar; si no se indica, se usa la hora actual.
    La fecha de cierre tiene prioridad: pasada esa fecha, la encuesta queda
    cerrada aunque en el panel figure como abierta.
    """
    cfg = configuracion()
    ahora = ahora or datetime.now(timezone.utc)
    if cfg is None:
        return CERRADA
    if ahora >= _utc(cfg.fecha_cierre):
        return CERRADA
    if cfg.fecha_publicacion is None:
        return PRUEBA
    return ABIERTA if cfg.encuesta_abierta else CERRADA
