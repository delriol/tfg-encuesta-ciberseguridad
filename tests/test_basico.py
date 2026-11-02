import pytest

from app import create_app


def test_inicio_responde(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Encuesta de ciberseguridad" in resp.get_data(as_text=True)


def test_salud_con_base(client):
    resp = client.get("/salud")
    assert resp.status_code == 200
    assert resp.get_json() == {"estado": "ok"}


def test_cabeceras_de_seguridad(client):
    resp = client.get("/")
    assert "max-age" in resp.headers["Strict-Transport-Security"]
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in resp.headers["Content-Security-Policy"]


def test_falta_secret_key(monkeypatch):
    from app.config import TestConfig

    class SinClave(TestConfig):
        SECRET_KEY = None

    with pytest.raises(RuntimeError):
        create_app(SinClave)


def test_normaliza_url_de_neon():
    from app.config import _normalizar_url

    assert _normalizar_url("postgresql://u:c@h/db?sslmode=require").startswith("postgresql+psycopg://")
    assert _normalizar_url("postgres://u:c@h/db").startswith("postgresql+psycopg://")
