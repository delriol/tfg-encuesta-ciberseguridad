"""Exportación a CSV pensada para Excel en español: separador ';', coma decimal y UTF-8 con BOM."""
import csv
import io
from zoneinfo import ZoneInfo

from .models import Item, Respuesta
from .puntajes import puntajes_de

ARGENTINA = ZoneInfo("America/Argentina/Buenos_Aires")


def hora_argentina(dt):
    if dt is None:
        return ""
    if dt.tzinfo is None:
        from datetime import timezone
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ARGENTINA).strftime("%Y-%m-%d %H:%M:%S")


def _numero(v):
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".").replace(".", ",")
    return v


def _csv(filas, encabezado):
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(encabezado)
    for fila in filas:
        w.writerow([_numero(v) for v in fila])
    return buf.getvalue()


def _respuestas_enviadas():
    return (Respuesta.query.filter(Respuesta.enviada_en.isnot(None))
            .order_by(Respuesta.enviada_en).all())


def _por_item(r):
    datos = {}
    for d in r.detalles:
        if d.texto_libre is not None:
            datos[d.item_codigo] = d.texto_libre
        else:
            datos.setdefault(d.item_codigo, []).append(d.opcion.codigo)
    return datos


def _base(r):
    duracion = int((r.enviada_en - r.iniciada_en).total_seconds()) if r.enviada_en else ""
    return [r.id, r.origen.codigo, hora_argentina(r.iniciada_en),
            hora_argentina(r.enviada_en), duracion, r.version_consentimiento]


BASE = ["id", "origen", "iniciada_en", "enviada_en", "duracion_segundos", "version_consentimiento"]


def csv_respuestas():
    """Una fila por persona. Preguntas de una opción: código elegido. Múltiples: una columna 0/1 por opción."""
    items = Item.query.order_by(Item.seccion, Item.orden).all()
    columnas = []
    for it in items:
        if it.tipo_respuesta == "multiple":
            columnas += [(it, op.codigo) for op in it.opciones]
        else:
            columnas.append((it, None))
    encabezado = BASE + [f"{it.codigo}_{op}" if op else it.codigo for it, op in columnas]
    filas = []
    for r in _respuestas_enviadas():
        datos = _por_item(r)
        fila = _base(r)
        for it, op in columnas:
            valor = datos.get(it.codigo)
            if op is not None:
                fila.append(1 if valor and op in valor else 0)
            elif isinstance(valor, list):
                fila.append(valor[0])
            else:
                fila.append(valor or "")
        filas.append(fila)
    return _csv(filas, encabezado)


def csv_puntajes():
    """Una fila por persona con datos generales e índices ya calculados."""
    items = {it.codigo: it for it in Item.query.all()}
    generales = [c for c in ("D1", "D2", "D3", "D4", "D6") if c in items]
    d5 = [op.codigo for op in items["D5"].opciones] if "D5" in items else []
    filas, encabezado = [], None
    for r in _respuestas_enviadas():
        datos = _por_item(r)
        pts = puntajes_de({k: v for k, v in datos.items() if isinstance(v, list)}, items)
        if encabezado is None:
            encabezado = BASE + generales + [f"D5_{c}" for c in d5] + list(pts.keys())
        fila = _base(r) + [(datos.get(c) or [""])[0] for c in generales]
        fila += [1 if c in datos.get("D5", []) else 0 for c in d5]
        fila += list(pts.values())
        filas.append(fila)
    if encabezado is None:
        encabezado = BASE + generales + [f"D5_{c}" for c in d5] + list(puntajes_de({}, items).keys())
    return _csv(filas, encabezado)

