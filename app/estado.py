"""Estado de la encuesta según la configuración y la hora actual."""
from datetime import datetime, timezone

from . import db
from .models import Configuracion

PRUEBA = "prueba"      # todavía no se publicó: funciona, pero los datos se borran al publicar
ABIERTA = "abierta"
CERRADA = "cerrada"


def _utc(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def configuracion():
    return db.session.get(Configuracion, 1)


def estado_encuesta(ahora=None):
    cfg = configuracion()
    ahora = ahora or datetime.now(timezone.utc)
    if cfg is None:
        return CERRADA
    if ahora >= _utc(cfg.fecha_cierre):
        return CERRADA
    if cfg.fecha_publicacion is None:
        return PRUEBA
    return ABIERTA if cfg.encuesta_abierta else CERRADA
