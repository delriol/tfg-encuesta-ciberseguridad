"""Validación de un envío de la encuesta contra el catálogo de la base."""
from .models import Item

LARGO_MAXIMO_ABIERTA = 1000
UNA_OPCION = {"unica", "desplegable", "vf", "likert", "frecuencia"}


def items_del_catalogo():
    return Item.query.order_by(Item.seccion, Item.orden).all()


def validar_envio(form, items):
    """Devuelve (elegidas, errores).

    elegidas: {codigo_item: [Opcion, ...] o str (pregunta abierta)}
    errores: {codigo_item: mensaje}
    """
    elegidas, errores = {}, {}
    for item in items:
        por_codigo = {o.codigo: o for o in item.opciones}
        if item.tipo_respuesta == "abierta":
            texto = (form.get(item.codigo) or "").strip()
            if len(texto) > LARGO_MAXIMO_ABIERTA:
                errores[item.codigo] = f"Usá como máximo {LARGO_MAXIMO_ABIERTA} caracteres."
            elif texto:
                elegidas[item.codigo] = texto
            elif item.obligatorio:
                errores[item.codigo] = "Falta responder esta pregunta."
            continue

        valores = form.getlist(item.codigo)
        if item.tipo_respuesta in UNA_OPCION and len(valores) > 1:
            errores[item.codigo] = "Elegí una sola opción."
            continue
        if any(v not in por_codigo for v in valores) or len(set(valores)) != len(valores):
            errores[item.codigo] = "La opción elegida no es válida."
            continue
        opciones = [por_codigo[v] for v in valores]
        if not opciones:
            if item.obligatorio:
                errores[item.codigo] = "Falta responder esta pregunta."
            continue
        if len(opciones) > 1 and any(o.excluyente for o in opciones):
            excl = next(o for o in opciones if o.excluyente)
            errores[item.codigo] = f"Si elegís “{excl.texto}”, no marques otras opciones."
            continue
        elegidas[item.codigo] = opciones
    return elegidas, errores
