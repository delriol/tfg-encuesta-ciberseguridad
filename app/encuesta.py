"""Rutas públicas de la encuesta: portada, consentimiento, cuestionario y cierre.

Recorrido de una persona:

1. Entra a la portada (/), opcionalmente con ?origen=whatsapp o ?origen=facebook.
2. Indica si es mayor de 18 y acepta participar (/consentimiento). Recién ahí
   se crea su registro y se le asigna una cookie que identifica al navegador.
3. Completa el cuestionario (/encuesta), que se valida en el servidor.
4. Ve el agradecimiento (/gracias). Si vuelve a entrar, se le avisa que ya
   respondió.
"""
import uuid
from datetime import datetime, timezone

from flask import (Blueprint, current_app, make_response, redirect, render_template, request,
                   session, url_for)

from . import db
from .catalogo import leer_catalogo
from .estado import CERRADA, PRUEBA, configuracion, estado_encuesta
from .models import DetalleRespuesta, Origen, Rechazo, Respuesta
from .validacion import items_del_catalogo, validar_envio

bp = Blueprint("encuesta", __name__)

# Cookie que guarda el identificador al azar de la participación (sin datos personales).
COOKIE = "tfg_participante"
DURACION_COOKIE = 60 * 60 * 24 * 60  # 60 días: cubre toda la recolección
ORIGENES_VALIDOS = {"whatsapp", "facebook"}
# Campo trampa ("honeypot"): está oculto para las personas, así que si llega
# completo lo llenó un programa automático y el envío se descarta.
HONEYPOT = "sitio_web"


def _origen_actual():
    """Origen guardado en la sesión al entrar a la portada; si no hay, "directo"."""
    codigo = session.get("origen", "directo")
    return Origen.query.filter_by(codigo=codigo).first() or Origen.query.filter_by(codigo="directo").one()


def _respuesta_del_navegador():
    """Busca la participación asociada a la cookie de este navegador (o None)."""
    valor = request.cookies.get(COOKIE)
    if not valor:
        return None
    try:
        token = uuid.UUID(valor)
    except ValueError:
        return None
    return Respuesta.query.filter_by(token_navegador=token).first()


def _contexto():
    """Datos comunes a todas las páginas: si se muestra el aviso de modo prueba."""
    return {"modo_prueba": estado_encuesta() == PRUEBA}


def _secciones():
    """Títulos de las secciones del cuestionario, tomados del archivo JSON."""
    return leer_catalogo()["secciones"]


@bp.get("/")
def portada():
    """Página de inicio con la presentación y el consentimiento.

    Registra el origen del enlace y deriva según el caso: encuesta cerrada,
    persona que ya respondió o persona que empezó y no terminó.
    """
    origen = request.args.get("origen", "").lower()
    if origen in ORIGENES_VALIDOS:
        session["origen"] = origen
    elif "origen" not in session:
        session["origen"] = "directo"

    estado = estado_encuesta()
    if estado == CERRADA:
        cfg = configuracion()
        return render_template("cerrada.html", publicada=bool(cfg and cfg.fecha_publicacion), **_contexto())
    previa = _respuesta_del_navegador()
    if previa and previa.enviada_en:
        return render_template("ya_respondiste.html", **_contexto())
    if previa:
        return redirect(url_for("encuesta.cuestionario"))
    return render_template("portada.html", **_contexto())


@bp.post("/consentimiento")
def consentimiento():
    """Procesa la respuesta de la portada.

    - "No participar": se registra el rechazo y se agradece.
    - Menor de 18: se registra el rechazo y no se continúa.
    - Mayor de 18 y acepta: se crea la participación y se pasa al cuestionario.
    """
    if estado_encuesta() == CERRADA:
        return redirect(url_for("encuesta.portada"))
    previa = _respuesta_del_navegador()
    if previa:
        return redirect(url_for("encuesta.portada"))

    accion = request.form.get("accion")
    edad = request.form.get("mayor_18")  # "si", "no" o vacío si no eligió
    acepta = request.form.get("acepta") == "si"

    if accion == "no_participar":
        db.session.add(Rechazo(motivo="no_acepta", origen=_origen_actual()))
        db.session.commit()
        return render_template("sin_participar.html", motivo="no_acepta", **_contexto())
    if accion != "comenzar":
        return redirect(url_for("encuesta.portada"))
    if edad == "no":
        db.session.add(Rechazo(motivo="menor", origen=_origen_actual()))
        db.session.commit()
        return render_template("sin_participar.html", motivo="menor", **_contexto())
    if edad != "si":
        # Si no eligió Sí ni No, se le pide que conteste; no se cuenta como menor.
        return render_template("portada.html", error="Para comenzar indicá si tenés 18 años o más.",
                               **_contexto()), 400
    if not acepta:
        return render_template("portada.html", error="Para comenzar tenés que aceptar participar.",
                               **_contexto()), 400

    origen = _origen_actual()
    r = Respuesta(origen=origen, token_navegador=uuid.uuid4(),
                  version_consentimiento=configuracion().version_consentimiento)
    db.session.add(r)
    db.session.commit()
    resp = make_response(redirect(url_for("encuesta.cuestionario")))
    resp.set_cookie(COOKIE, str(r.token_navegador), max_age=DURACION_COOKIE, httponly=True,
                    secure=current_app.config["SESSION_COOKIE_SECURE"], samesite="Lax")
    return resp


@bp.route("/encuesta", methods=["GET", "POST"])
def cuestionario():
    """Muestra el cuestionario (GET) y guarda las respuestas (POST).

    Si hay errores se vuelve a mostrar con lo ya contestado y un aviso en cada
    pregunta con problemas. Cada participación se puede enviar una sola vez.
    """
    if estado_encuesta() == CERRADA:
        return redirect(url_for("encuesta.portada"))
    r = _respuesta_del_navegador()
    if r is None:
        return redirect(url_for("encuesta.portada"))
    if r.enviada_en:
        return render_template("ya_respondiste.html", **_contexto())

    items = items_del_catalogo()
    if request.method == "GET":
        return render_template("encuesta.html", items=items, errores={}, valores=None, secciones=_secciones(), **_contexto())

    if request.form.get(HONEYPOT):
        return redirect(url_for("encuesta.gracias"))  # se descarta sin avisar al bot

    elegidas, errores = validar_envio(request.form, items)
    if errores:
        return render_template("encuesta.html", items=items, errores=errores, valores=request.form,
                               secciones=_secciones(),
                               **_contexto()), 400

    # Marca el envío solo si nadie lo marcó antes (doble clic o dos pestañas).
    marcadas = (Respuesta.query.filter_by(id=r.id, enviada_en=None)
                .update({"enviada_en": datetime.now(timezone.utc)}, synchronize_session=False))
    if marcadas != 1:
        db.session.rollback()
        return render_template("ya_respondiste.html", **_contexto())
    # Se guarda una fila por opción elegida, o el texto de la pregunta abierta.
    for codigo, valor in elegidas.items():
        if isinstance(valor, str):
            db.session.add(DetalleRespuesta(respuesta_id=r.id, item_codigo=codigo, texto_libre=valor))
        else:
            for op in valor:
                db.session.add(DetalleRespuesta(respuesta_id=r.id, item_codigo=codigo, opcion_id=op.id))
    db.session.commit()
    return redirect(url_for("encuesta.gracias"))


@bp.get("/gracias")
def gracias():
    """Página de agradecimiento al terminar."""
    return render_template("gracias.html", **_contexto())
