from datetime import datetime, timedelta, timezone

import pytest

from app import db
from app.catalogo import cargar_catalogo, sembrar_base
from app.models import Configuracion, Respuesta, VisitaQR
from app.qr import COOKIE_VISITANTE
from tests.test_encuesta import respuestas_validas
from tests.test_panel import ingresar
from werkzeug.security import generate_password_hash
from app.models import UsuarioAdmin
from tests.test_panel import CLAVE


@pytest.fixture
def base(app):
    sembrar_base()
    cargar_catalogo()
    db.session.add(UsuarioAdmin(usuario="leandro", hash_clave=generate_password_hash(CLAVE)))
    db.session.commit()
    return app


def test_visita_se_cuenta(base, client):
    resp = client.get("/qr")
    html = resp.get_data(as_text=True)
    assert "El repositorio de apuntes y exámenes del cartel no existe" in html
    assert "origen=qr" in html
    assert resp.headers["Cache-Control"] == "no-store"
    assert VisitaQR.query.count() == 1


def test_mismo_visitante_dos_veces(base, client):
    client.get("/qr")
    client.get("/qr")
    otro = base.test_client()
    otro.get("/qr")
    assert VisitaQR.query.count() == 3
    assert db.session.query(VisitaQR.token_visitante).distinct().count() == 2
    assert client.get_cookie(COOKIE_VISITANTE).http_only


def test_qr_lleva_a_encuesta_con_origen_qr(base, client):
    client.get("/qr")
    client.get("/?origen=qr")
    client.post("/consentimiento", data={"mayor_18": "si", "acepta": "si", "accion": "comenzar"})
    client.post("/encuesta", data=respuestas_validas())
    r = Respuesta.query.one()
    assert r.desde_qr and r.enviada_en


def test_qr_con_encuesta_cerrada(base, client):
    cfg = db.session.get(Configuracion, 1)
    cfg.fecha_cierre = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.session.commit()
    html = client.get("/qr").get_data(as_text=True)
    assert "no existe" in html and "Responder la encuesta" not in html
    assert VisitaQR.query.count() == 0


def test_difusion_y_codigo(base, client):
    assert client.get("/panel/codigo-qr.png").status_code == 302  # requiere ingreso
    ingresar(client)
    html = client.get("/panel/difusion").get_data(as_text=True)
    assert "https://localhost/qr" in html and "origen=whatsapp" in html and "origen=facebook" in html
    png = client.get("/panel/codigo-qr.png")
    assert png.mimetype == "image/png" and png.data[:4] == b"\x89PNG"
    assert client.get("/panel/codigo-qr.svg").mimetype == "image/svg+xml"
    cartel = client.get("/panel/cartel").get_data(as_text=True)
    assert "Repositorio de apuntes y exámenes" in cartel and "<svg" in cartel


def test_url_publica_configurable(base, client, monkeypatch):
    monkeypatch.setenv("PUBLIC_URL", "https://encuesta.ejemplo.com/")
    ingresar(client)
    assert "https://encuesta.ejemplo.com/qr" in client.get("/panel/difusion").get_data(as_text=True)
