import csv
import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from werkzeug.security import generate_password_hash

from app import db
from app.catalogo import cargar_catalogo, sembrar_base
from app.models import Configuracion, Item, Rechazo, Respuesta, UsuarioAdmin, VisitaQR
from app.puntajes import nivel, puntajes_de
from tests.test_encuesta import aceptar, respuestas_validas

CLAVE = "una-clave-larga-de-prueba"


@pytest.fixture
def base(app):
    sembrar_base()
    cargar_catalogo()
    db.session.add(UsuarioAdmin(usuario="leandro", hash_clave=generate_password_hash(CLAVE)))
    db.session.commit()
    return app


def ingresar(client, clave=CLAVE):
    return client.post("/panel/ingresar", data={"usuario": "leandro", "clave": clave})


def leer_csv(resp):
    texto = resp.get_data(as_text=True)
    assert texto.startswith("﻿")
    return list(csv.DictReader(io.StringIO(texto[1:]), delimiter=";"))


def responder(app, origen=None, **cambios):
    c = app.test_client()
    aceptar(c, origen)
    c.post("/encuesta", data=respuestas_validas(**cambios))
    return c


# --- acceso ---------------------------------------------------------------

def test_panel_pide_ingreso(base, client):
    assert client.get("/panel").headers["Location"].endswith("/panel/ingresar")
    assert client.get("/panel/exportar/respuestas.csv").status_code == 302


def test_ingreso_correcto(base, client):
    assert ingresar(client).headers["Location"].endswith("/panel")
    assert "Panel del investigador" in client.get("/panel").get_data(as_text=True)


def test_clave_incorrecta(base, client):
    assert ingresar(client, "otra").status_code == 401
    assert client.get("/panel").status_code == 302


def test_bloqueo_tras_5_intentos(base, client):
    for _ in range(5):
        ingresar(client, "mal")
    resp = ingresar(client)  # aun con la clave correcta
    assert "Demasiados intentos" in resp.get_data(as_text=True)
    u = UsuarioAdmin.query.one()
    u.bloqueado_hasta = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.session.commit()
    assert ingresar(client).status_code == 302


def test_sesion_vence(base, client):
    ingresar(client)
    with client.session_transaction() as s:
        s["admin_desde"] = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    assert client.get("/panel").status_code == 302


# --- indicadores y exportación ------------------------------------------

def test_indicadores(base, client):
    responder(base, "qr")
    responder(base, "whatsapp")
    c = base.test_client()
    aceptar(c)  # empezó y no envió
    c.post("/consentimiento", data={"accion": "no_participar"})
    t = uuid.uuid4()
    db.session.add_all([VisitaQR(token_visitante=t), VisitaQR(token_visitante=t),
                        VisitaQR(token_visitante=uuid.uuid4())])
    db.session.commit()
    ingresar(client)
    html = client.get("/panel").get_data(as_text=True)
    assert ">2<" in html  # enviadas
    assert "2 visitantes únicos" in html
    assert "50.0%" in html  # 1 enviada desde QR / 2 visitantes únicos
    assert "QR 1 · WhatsApp 1" in html


def test_csv_respuestas(base, client):
    responder(base, "facebook", Q1=["S1", "G2"], D5=["1", "3"], E1=["8"])
    ingresar(client)
    filas = leer_csv(client.get("/panel/exportar/respuestas.csv"))
    assert len(filas) == 1
    f = filas[0]
    assert f["origen"] == "facebook" and f["desde_qr"] == "0"
    assert f["Q1_S1"] == "1" and f["Q1_G2"] == "1" and f["Q1_S2"] == "0"
    assert f["D5_1"] == "1" and f["D5_2"] == "0" and f["D5_3"] == "1"
    assert f["E1_8"] == "1" and f["E1_1"] == "0"
    assert f["K1"] == "V" and f["P1"].startswith("Quiero")
    assert int(f["duracion_segundos"]) >= 0


def test_csv_puntajes(base, client):
    # Todas las K correctas, Q2 correcta, 15 términos de seguridad, A y B en 5 salvo invertidos en 1.
    clave = {f"K{i}": c for i, c in enumerate("VFFVFVVFVV", start=1)}
    likert = {f"A{i}": "5" for i in range(1, 10)} | {f"B{i}": "5" for i in range(1, 11)}
    likert.update({"A5": "1", "B5": "1", "B6": "1"})
    responder(base, Q1=[f"S{i}" for i in range(1, 16)], Q2="2", **clave, **likert)
    ingresar(client)
    f = leer_csv(client.get("/panel/exportar/puntajes.csv"))[0]
    for col in ("IC", "IA", "IB", "ICC", "Reconocer", "Enfrentar", "Mitigar"):
        assert f[col] == "100", col
    assert f["nivel_ICC"] == "bueno"
    assert f["K_aciertos"] == "10" and f["K_no_se"] == "0"


def test_puntajes_a_mano():
    """Un caso calculado a mano, como pide la capa 5 del plan de pruebas."""
    class I:
        def __init__(self, tipo, suma=True, correcta=None, inv=False):
            self.tipo_respuesta, self.suma_al_indice, self.respuesta_correcta, self.invertido = tipo, suma, correcta, inv
    items = {"Q1": I("multiple"), "Q2": I("unica", correcta="2")}
    items |= {f"K{i}": I("vf", correcta="V") for i in range(1, 11)}
    items |= {f"A{i}": I("likert", inv=(i == 5), suma=(i != 6)) for i in range(1, 10)}
    items |= {f"B{i}": I("frecuencia", inv=i in (5, 6), suma=(i != 4)) for i in range(1, 11)}
    resp = {"Q1": ["S1", "S2", "S3", "G1"], "Q2": ["1"]}
    resp |= {f"K{i}": ["V"] for i in range(1, 6)} | {f"K{i}": ["NS"] for i in range(6, 11)}
    resp |= {f"A{i}": ["3"] for i in range(1, 10)} | {f"B{i}": ["4"] for i in range(1, 11)}
    p = puntajes_de(resp, items)
    # IC = (3/15 + 0 + 5·1 + 5·0) / 12 = 5,2 / 12 = 43,3
    assert p["IC"] == 43.3 and p["K_no_se"] == 5 and p["Q1_terminos_seguridad"] == 3
    assert p["IA"] == 50.0  # todos 3 (A5 invertido también da 3)
    # B: 7 ítems en 4 → 0,75; B5 y B6 invertidos: 6−4=2 → 0,25. (7·0,75 + 2·0,25)/9 = 63,9
    assert p["IB"] == 63.9
    assert p["ICC"] == round(0.3 * 43.3 + 0.2 * 50 + 0.5 * 63.9, 1)
    assert nivel(p["ICC"]) == "bajo" and nivel(60) == "medio" and nivel(80) == "bueno"


def test_csv_visitas(base, client):
    db.session.add(VisitaQR(token_visitante=uuid.uuid4()))
    db.session.commit()
    ingresar(client)
    assert len(leer_csv(client.get("/panel/exportar/visitas.csv"))) == 1


# --- publicar -------------------------------------------------------------

def test_publicar_borra_pruebas(base, client):
    responder(base)
    db.session.add(Rechazo(motivo="menor", origen_id=1))
    db.session.add(VisitaQR(token_visitante=uuid.uuid4()))
    db.session.commit()
    ingresar(client)
    client.post("/panel/publicar", data={"confirmacion": "publicar"})
    cfg = db.session.get(Configuracion, 1)
    assert cfg.fecha_publicacion is not None and cfg.encuesta_abierta
    assert Respuesta.query.count() == 0 and Rechazo.query.count() == 0 and VisitaQR.query.count() == 0
    assert Item.query.count() == 40  # el cuestionario queda
    assert client.post("/panel/publicar", data={"confirmacion": "PUBLICAR"}).status_code == 409


def test_publicar_exige_confirmacion(base, client):
    ingresar(client)
    client.post("/panel/publicar", data={"confirmacion": "si"})
    assert db.session.get(Configuracion, 1).fecha_publicacion is None


def test_pausar_y_reanudar(base, client):
    ingresar(client)
    assert client.post("/panel/estado", data={"abrir": "no"}).status_code == 409  # sin publicar
    client.post("/panel/publicar", data={"confirmacion": "PUBLICAR"})
    client.post("/panel/estado", data={"abrir": "no"})
    assert "cerró" in base.test_client().get("/").get_data(as_text=True)
    client.post("/panel/estado", data={"abrir": "si"})
    assert "Comenzar la encuesta" in base.test_client().get("/").get_data(as_text=True)
