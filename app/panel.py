"""Panel del investigador: acceso, indicadores, exportaciones y publicación."""
from datetime import datetime, timedelta, timezone
from functools import wraps

import os

from flask import (Blueprint, Response, abort, flash, redirect, render_template, request, session,
                   url_for)
from sqlalchemy import func
from werkzeug.security import check_password_hash

from . import db
from .estado import PRUEBA, _utc, configuracion, estado_encuesta
from .exportar import ARGENTINA, csv_puntajes, csv_respuestas, hora_argentina
from .models import DetalleRespuesta, Origen, Rechazo, Respuesta, UsuarioAdmin

bp = Blueprint("panel", __name__, url_prefix="/panel")

MAX_INTENTOS = 5
BLOQUEO = timedelta(minutes=15)
DURACION_SESION = timedelta(hours=2)


def requiere_admin(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        inicio = session.get("admin_desde")
        if not session.get("admin_id") or not inicio or \
                datetime.now(timezone.utc) - datetime.fromisoformat(inicio) > DURACION_SESION:
            session.pop("admin_id", None)
            return redirect(url_for("panel.ingresar"))
        return vista(*args, **kwargs)
    return envoltura


@bp.route("/ingresar", methods=["GET", "POST"])
def ingresar():
    error = None
    if request.method == "POST":
        ahora = datetime.now(timezone.utc)
        u = UsuarioAdmin.query.filter_by(usuario=request.form.get("usuario", "")).first()
        if u and u.bloqueado_hasta and _utc(u.bloqueado_hasta) > ahora:
            error = "Demasiados intentos. Probá de nuevo en 15 minutos."
        elif u and check_password_hash(u.hash_clave, request.form.get("clave", "")):
            u.intentos_fallidos = 0
            u.bloqueado_hasta = None
            db.session.commit()
            session.clear()
            session["admin_id"] = u.id
            session["admin_desde"] = ahora.isoformat()
            return redirect(url_for("panel.inicio"))
        else:
            if u:
                u.intentos_fallidos += 1
                if u.intentos_fallidos >= MAX_INTENTOS:
                    u.bloqueado_hasta = ahora + BLOQUEO
                    u.intentos_fallidos = 0
                db.session.commit()
            error = "Usuario o clave incorrectos."
    return render_template("panel_ingresar.html", error=error), (401 if error else 200)


@bp.post("/salir")
def salir():
    session.clear()
    return redirect(url_for("panel.ingresar"))


def indicadores():
    enviadas = Respuesta.query.filter(Respuesta.enviada_en.isnot(None))
    total_enviadas = enviadas.count()
    por_origen = dict(db.session.query(Origen.codigo, func.count(Respuesta.id))
                      .join(Respuesta, Respuesta.origen_id == Origen.id)
                      .filter(Respuesta.enviada_en.isnot(None)).group_by(Origen.codigo).all())
    rechazos = dict(db.session.query(Rechazo.motivo, func.count(Rechazo.id)).group_by(Rechazo.motivo).all())
    duraciones = [(r.enviada_en - r.iniciada_en).total_seconds() for r in enviadas.all()]
    duraciones.sort()
    mediana = duraciones[len(duraciones) // 2] / 60 if duraciones else None

    por_dia = {}
    for r in enviadas.all():
        dia = _utc(r.enviada_en).astimezone(ARGENTINA).date()
        por_dia[dia] = por_dia.get(dia, 0) + 1

    cfg = configuracion()
    dias_publicada = None
    if cfg.fecha_publicacion:
        fin = min(datetime.now(timezone.utc), _utc(cfg.fecha_cierre))
        dias_publicada = (fin - _utc(cfg.fecha_publicacion)).days + 1
    return {
        "enviadas": total_enviadas,
        "sin_enviar": Respuesta.query.filter(Respuesta.enviada_en.is_(None)).count(),
        "por_origen": por_origen,
        "rechazo_no_acepta": rechazos.get("no_acepta", 0),
        "rechazo_menor": rechazos.get("menor", 0),
        "mediana_minutos": round(mediana, 1) if mediana is not None else None,
        "por_dia": sorted(por_dia.items()),
        "dias_publicada": dias_publicada,
    }


@bp.get("")
@requiere_admin
def inicio():
    cfg = configuracion()
    return render_template("panel.html", ind=indicadores(), estado=estado_encuesta(), cfg=cfg,
                           publicada=hora_argentina(cfg.fecha_publicacion),
                           cierre=hora_argentina(cfg.fecha_cierre), modo_prueba=False)


def _descarga(contenido, nombre):
    sello = datetime.now(ARGENTINA).strftime("%Y%m%d-%H%M")
    return Response(contenido, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename={nombre}-{sello}.csv",
                             "Cache-Control": "no-store"})


@bp.get("/exportar/respuestas.csv")
@requiere_admin
def exportar_respuestas():
    return _descarga(csv_respuestas(), "respuestas")


@bp.get("/exportar/puntajes.csv")
@requiere_admin
def exportar_puntajes():
    return _descarga(csv_puntajes(), "puntajes")


@bp.post("/publicar")
@requiere_admin
def publicar():
    """Borra los datos de prueba, registra la fecha real de publicación y abre la encuesta. Una sola vez."""
    cfg = configuracion()
    if estado_encuesta() != PRUEBA:
        abort(409)
    if request.form.get("confirmacion", "").strip().upper() != "PUBLICAR":
        flash("Para publicar escribí PUBLICAR en el recuadro.")
        return redirect(url_for("panel.inicio"))
    DetalleRespuesta.query.delete()
    Respuesta.query.delete()
    Rechazo.query.delete()
    cfg.fecha_publicacion = datetime.now(timezone.utc)
    cfg.encuesta_abierta = True
    db.session.commit()
    flash("Encuesta publicada. Se borraron los datos de prueba.")
    return redirect(url_for("panel.inicio"))


@bp.post("/estado")
@requiere_admin
def cambiar_estado():
    """Pausa o reanuda la encuesta ya publicada (por ejemplo, ante un problema)."""
    cfg = configuracion()
    if cfg.fecha_publicacion is None:
        abort(409)
    cfg.encuesta_abierta = request.form.get("abrir") == "si"
    db.session.commit()
    flash("Encuesta reanudada." if cfg.encuesta_abierta else "Encuesta pausada.")
    return redirect(url_for("panel.inicio"))


def url_publica(endpoint, **valores):
    """Dirección completa que se difunde. PUBLIC_URL permite fijarla si se usa un dominio propio."""
    base = os.environ.get("PUBLIC_URL", "").rstrip("/")
    ruta = url_for(endpoint, **valores)
    return base + ruta if base else url_for(endpoint, _external=True, _scheme="https", **valores)


@bp.get("/difusion")
@requiere_admin
def difusion():
    enlaces = {
        "WhatsApp": url_publica("encuesta.portada", origen="whatsapp"),
        "Facebook": url_publica("encuesta.portada", origen="facebook"),
    }
    return render_template("panel_difusion.html", enlaces=enlaces, modo_prueba=False)

