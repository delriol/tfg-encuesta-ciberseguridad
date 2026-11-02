"""Página de destino del experimento QR: cuenta la visita y revela el propósito académico."""
import uuid

from flask import Blueprint, current_app, make_response, render_template, request

from . import db
from .estado import CERRADA, PRUEBA, estado_encuesta
from .models import VisitaQR

bp = Blueprint("qr", __name__)

COOKIE_VISITANTE = "tfg_visitante"
DURACION = 60 * 60 * 24 * 60


def _token_visitante():
    try:
        return uuid.UUID(request.cookies.get(COOKIE_VISITANTE, "")), False
    except ValueError:
        return uuid.uuid4(), True


@bp.get("/qr")
def pagina_qr():
    estado = estado_encuesta()
    token, nuevo = _token_visitante()
    if estado != CERRADA:
        # Solo fecha, hora y un identificador aleatorio del navegador. Nada más.
        db.session.add(VisitaQR(token_visitante=token))
        db.session.commit()
    resp = make_response(render_template("qr.html", abierta=estado != CERRADA,
                                         modo_prueba=estado == PRUEBA))
    resp.headers["Cache-Control"] = "no-store"  # cada escaneo tiene que llegar al servidor
    if nuevo:
        resp.set_cookie(COOKIE_VISITANTE, str(token), max_age=DURACION, httponly=True,
                        secure=current_app.config["SESSION_COOKIE_SECURE"], samesite="Lax")
    return resp
