"""Validación de un envío de la encuesta contra el catálogo de la base.

El navegador también controla que no falten respuestas, pero no se puede
confiar solo en eso: esta validación en el servidor es la que decide si un
envío se guarda.
"""
from .models import Item

LARGO_MAXIMO_ABIERTA = 1000  # caracteres de la pregunta abierta (P1)
# Tipos de pregunta que admiten una sola opción elegida.
UNA_OPCION = {"unica", "desplegable", "vf", "likert", "frecuencia"}


def items_del_catalogo():
    """Devuelve todas las preguntas en el orden en que se muestran."""
    return Item.query.order_by(Item.seccion, Item.orden).all()


def validar_envio(form, items):
    """Revisa cada pregunta del formulario enviado.

    form: datos del formulario (request.form).
    items: preguntas del cuestionario.

    Devuelve (elegidas, errores):
    - elegidas: {codigo_pregunta: [Opcion, ...]}, o el texto escrito si es la
      pregunta abierta.
    - errores: {codigo_pregunta: mensaje para mostrar}. Si está vacío, el envío
      es válido.

    Se controla que estén las obligatorias, que las opciones existan, que no
    haya más de una donde va una sola y que una opción excluyente (por ejemplo
    "Ninguno") no venga junto con otras.
    """
    elegidas, errores = {}, {}
    for item in items:
        por_codigo = {o.codigo: o for o in item.opciones}

        # Pregunta abierta: texto libre con un largo máximo.
        if item.tipo_respuesta == "abierta":
            texto = (form.get(item.codigo) or "").strip()
            if len(texto) > LARGO_MAXIMO_ABIERTA:
                errores[item.codigo] = f"Usá como máximo {LARGO_MAXIMO_ABIERTA} caracteres."
            elif texto:
                elegidas[item.codigo] = texto
            elif item.obligatorio:
                errores[item.codigo] = "Falta responder esta pregunta."
            continue

        # Preguntas con opciones: una o varias, según el tipo.
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
