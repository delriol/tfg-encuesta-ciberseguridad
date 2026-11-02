from datetime import datetime, timedelta, timezone

import pytest
from werkzeug.datastructures import MultiDict

from app import db
from app.catalogo import cargar_catalogo, sembrar_base
from app.encuesta import COOKIE
from app.models import Configuracion, DetalleRespuesta, Item, Rechazo, Respuesta


@pytest.fixture
def base(app):
    sembrar_base()
    cargar_catalogo()
    return app


def respuestas_validas(**cambios):
    """Una respuesta completa: primera opción en cada pregunta, salvo los cambios."""
    datos = MultiDict()
    for item in Item.query.order_by(Item.seccion, Item.orden):
        if item.tipo_respuesta == "abierta":
            datos[item.codigo] = "Quiero aprender a detectar estafas."
        else:
            datos[item.codigo] = item.opciones[0].codigo
    for codigo, valor in cambios.items():
        datos.setlist(codigo, valor if isinstance(valor, list) else [valor])
    return datos


def aceptar(client, origen=None):
    if origen:
        client.get(f"/?origen={origen}")
    return client.post("/consentimiento", data={"mayor_18": "si", "acepta": "si", "accion": "comenzar"})


def publicar(cerrar=False):
    cfg = db.session.get(Configuracion, 1)
    cfg.fecha_publicacion = datetime.now(timezone.utc)
    cfg.encuesta_abierta = not cerrar
    db.session.commit()


def test_portada_en_modo_prueba(base, client):
    html = client.get("/").get_data(as_text=True)
    assert "Modo prueba" in html
    assert "Comenzar la encuesta" in html


def test_flujo_completo(base, client):
    resp = aceptar(client, "whatsapp")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/encuesta")
    assert client.get_cookie(COOKIE).http_only
    assert client.get("/encuesta").status_code == 200
    resp = client.post("/encuesta", data=respuestas_validas(Q1=["S1", "S2", "G1"]))
    assert resp.headers["Location"].endswith("/gracias")
    r = Respuesta.query.one()
    assert r.enviada_en is not None
    assert r.origen.codigo == "whatsapp" and not r.desde_qr
    q1 = {d.opcion.codigo for d in r.detalles if d.item_codigo == "Q1"}
    assert q1 == {"S1", "S2", "G1"}
    p1 = [d for d in r.detalles if d.item_codigo == "P1"][0]
    assert p1.texto_libre.startswith("Quiero")


def test_origen_qr_marca_desde_qr(base, client):
    aceptar(client, "qr")
    assert Respuesta.query.one().desde_qr


def test_origen_desconocido_es_directo(base, client):
    aceptar(client, "instagram")
    assert Respuesta.query.one().origen.codigo == "directo"


def test_no_responde_dos_veces(base, client):
    aceptar(client)
    client.post("/encuesta", data=respuestas_validas())
    assert "Ya respondiste" in client.get("/").get_data(as_text=True)
    resp = client.post("/encuesta", data=respuestas_validas())
    assert "Ya respondiste" in resp.get_data(as_text=True)
    assert DetalleRespuesta.query.filter_by(item_codigo="K1").count() == 1


def test_falta_obligatoria(base, client):
    aceptar(client)
    datos = respuestas_validas()
    del datos["K3"]
    resp = client.post("/encuesta", data=datos)
    assert resp.status_code == 400
    html = resp.get_data(as_text=True)
    assert "Falta responder esta pregunta." in html
    assert Respuesta.query.one().enviada_en is None
    assert DetalleRespuesta.query.count() == 0


def test_opcionales_pueden_quedar_vacias(base, client):
    aceptar(client)
    datos = respuestas_validas()
    del datos["Q1"]
    del datos["P1"]
    assert client.post("/encuesta", data=datos).status_code == 302


def test_opcion_inexistente(base, client):
    aceptar(client)
    resp = client.post("/encuesta", data=respuestas_validas(K1="X"))
    assert resp.status_code == 400


def test_dos_opciones_en_pregunta_unica(base, client):
    aceptar(client)
    resp = client.post("/encuesta", data=respuestas_validas(K1=["V", "F"]))
    assert resp.status_code == 400


def test_ninguno_excluye_otras(base, client):
    aceptar(client)
    resp = client.post("/encuesta", data=respuestas_validas(E1=["1", "8"]))
    assert resp.status_code == 400
    assert "Ninguno" in resp.get_data(as_text=True)


def test_situacion_laboral_multiple(base, client):
    aceptar(client)
    assert client.post("/encuesta", data=respuestas_validas(D5=["1", "2"])).status_code == 302


def test_texto_abierto_largo(base, client):
    aceptar(client)
    resp = client.post("/encuesta", data=respuestas_validas(P1="a" * 1001))
    assert resp.status_code == 400


def test_honeypot_descarta(base, client):
    aceptar(client)
    datos = respuestas_validas()
    datos["sitio_web"] = "http://spam"
    client.post("/encuesta", data=datos)
    assert Respuesta.query.one().enviada_en is None


def test_menor_de_18(base, client):
    resp = client.post("/consentimiento", data={"acepta": "si", "accion": "comenzar"})
    assert "solo para personas de 18" in resp.get_data(as_text=True)
    assert Rechazo.query.one().motivo == "menor"
    assert Respuesta.query.count() == 0


def test_no_quiere_participar(base, client):
    client.post("/consentimiento", data={"accion": "no_participar"})
    assert Rechazo.query.one().motivo == "no_acepta"


def test_falta_aceptar(base, client):
    resp = client.post("/consentimiento", data={"mayor_18": "si", "accion": "comenzar"})
    assert resp.status_code == 400
    assert Respuesta.query.count() == 0 and Rechazo.query.count() == 0


def test_sin_consentimiento_no_entra(base, client):
    assert client.get("/encuesta").headers["Location"].endswith("/")


def test_encuesta_cerrada_por_fecha(base, client):
    cfg = db.session.get(Configuracion, 1)
    cfg.fecha_cierre = datetime.now(timezone.utc) - timedelta(minutes=1)
    publicar()
    assert "cerró el lunes 16" in client.get("/").get_data(as_text=True)
    assert client.post("/consentimiento", data={"mayor_18": "si", "acepta": "si",
                                                "accion": "comenzar"}).status_code == 302
    assert Respuesta.query.count() == 0


def test_cierre_corta_a_quien_estaba_respondiendo(base, client):
    aceptar(client)
    cfg = db.session.get(Configuracion, 1)
    cfg.fecha_cierre = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.session.commit()
    client.post("/encuesta", data=respuestas_validas())
    assert Respuesta.query.one().enviada_en is None


def test_publicada_sin_banner(base, client):
    publicar()
    assert "Modo prueba" not in client.get("/").get_data(as_text=True)


def test_pausada_manual(base, client):
    publicar(cerrar=True)
    assert "cerró" in client.get("/").get_data(as_text=True)


def test_encuesta_carga_navegacion_y_sin_estilos_en_linea(base, client):
    aceptar(client)
    html = client.get("/encuesta").get_data(as_text=True)
    assert "encuesta.js" in html and 'id="btn-siguiente"' in html
    assert "style=" not in html  # la CSP bloquea estilos en línea
    assert html.count('class="seccion') == 7
