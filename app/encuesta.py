"""Rutas públicas de la encuesta: portada, consentimiento, cuestionario y cierre."""
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

COOKIE = "tfg_participante"
DURACION_COOKIE = 60 * 60 * 24 * 60  # 60 días: cubre toda la recolección
ORIGENES_VALIDOS = {"whatsapp", "facebook"}
HONEYPOT = "sitio_web"  # campo oculto: si viene completo, es un bot


def _origen_actual():
    codigo = session.get("origen", "directo")
    return Origen.query.filter_by(codigo=codigo).first() or Origen.query.filter_by(codigo="directo").one()


def _respuesta_del_navegador():
    valor = request.cookies.get(COOKIE)
    if not valor:
        return None
    try:
        token = uuid.UUID(valor)
    except ValueError:
        return None
    return Respuesta.query.filter_by(token_navegador=token).first()


def _contexto():
    return {"modo_prueba": estado_encuesta() == PRUEBA}


def _secciones():
    return leer_catalogo()["secciones"]


@bp.get("/")
def portada():
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
    if estado_encuesta() == CERRADA:
        return redirect(url_for("encuesta.portada"))
    previa = _respuesta_del_navegador()
    if previa:
        return redirect(url_for("encuesta.portada"))

    accion = request.form.get("accion")
    mayor = request.form.get("mayor_18") == "si"
    acepta = request.form.get("acepta") == "si"

    if accion == "no_participar":
        db.session.add(Rechazo(motivo="no_acepta", origen=_origen_actual()))
        db.session.commit()
        return render_template("sin_participar.html", motivo="no_acepta", **_contexto())
    if accion != "comenzar":
        return redirect(url_for("encuesta.portada"))
    if not mayor:
        db.session.add(Rechazo(motivo="menor", origen=_origen_actual()))
        db.session.commit()
        return render_template("sin_participar.html", motivo="menor", **_contexto())
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
    return render_template("gracias.html", **_contexto())
