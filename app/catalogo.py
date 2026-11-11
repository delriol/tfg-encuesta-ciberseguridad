"""Carga del cuestionario (data/cuestionario_v03.json) y datos iniciales."""
import json
from datetime import datetime, timezone
from pathlib import Path

from . import db
from .models import Configuracion, Item, Opcion, Origen, Respuesta

RUTA_CATALOGO = Path(__file__).resolve().parent.parent / "data" / "cuestionario_v03.json"

ORIGENES = [
    ("whatsapp", "Enlace difundido por WhatsApp"),
    ("facebook", "Enlace difundido por Facebook"),
    ("directo", "Enlace sin etiqueta"),
]

# Lunes 16/11/2026 23:59:59 en Argentina (UTC-3) = 17/11/2026 02:59:59 UTC.
FECHA_CIERRE = datetime(2026, 11, 17, 2, 59, 59, tzinfo=timezone.utc)

# Opciones que excluyen a las demás de su pregunta.
EXCLUYENTES = {("E1", "8")}


def leer_catalogo(ruta=RUTA_CATALOGO):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def cargar_catalogo(ruta=RUTA_CATALOGO):
    """Inserta o actualiza preguntas y opciones. Se niega si ya hay respuestas guardadas."""
    if db.session.query(Respuesta.id).first() is not None:
        raise RuntimeError("Ya hay respuestas guardadas: el catálogo no se puede modificar.")
    datos = leer_catalogo(ruta)
    orden_por_seccion = {}
    codigos = set()
    for d in datos["items"]:
        orden_por_seccion[d["seccion"]] = orden_por_seccion.get(d["seccion"], 0) + 1
        codigos.add(d["codigo"])
        item = db.session.get(Item, d["codigo"]) or Item(codigo=d["codigo"])
        item.seccion = d["seccion"]
        item.orden = orden_por_seccion[d["seccion"]]
        item.texto = d["texto"]
        item.tipo_respuesta = d["tipo_respuesta"]
        item.obligatorio = d["obligatorio"]
        item.invertido = d["invertido"]
        item.suma_al_indice = d["suma_al_indice"]
        item.respuesta_correcta = d["respuesta_correcta"]
        existentes = {o.codigo: o for o in item.opciones}
        nuevas = []
        for o in d.get("opciones") or []:
            op = existentes.get(o["codigo"]) or Opcion(codigo=o["codigo"])
            op.texto = o["texto"]
            op.orden = o["orden"]
            op.grupo = o.get("grupo")
            op.excluyente = (d["codigo"], o["codigo"]) in EXCLUYENTES
            nuevas.append(op)
        item.opciones = nuevas
        db.session.add(item)
    for sobrante in Item.query.filter(Item.codigo.notin_(codigos)).all():
        db.session.delete(sobrante)
    db.session.commit()
    return len(codigos), Opcion.query.count()


def sembrar_base():
    """Orígenes y fila de configuración. Se puede correr varias veces."""
    for codigo, nombre in ORIGENES:
        if not Origen.query.filter_by(codigo=codigo).first():
            db.session.add(Origen(codigo=codigo, nombre=nombre))
    if not db.session.get(Configuracion, 1):
        db.session.add(Configuracion(id=1, fecha_cierre=FECHA_CIERRE, encuesta_abierta=False,
                                     version_consentimiento="1.0"))
    db.session.commit()
