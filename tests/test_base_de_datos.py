import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app import db
from app.catalogo import FECHA_CIERRE, cargar_catalogo, leer_catalogo, sembrar_base
from app.models import Configuracion, DetalleRespuesta, Item, Opcion, Origen, Respuesta


@pytest.fixture
def base(app):
    sembrar_base()
    cargar_catalogo()
    return app


def test_catalogo_completo(base):
    assert Item.query.count() == 40
    assert Opcion.query.count() == 212
    por_seccion = {s: Item.query.filter_by(seccion=s).count() for s in range(1, 8)}
    assert por_seccion == {1: 6, 2: 2, 3: 10, 4: 9, 5: 10, 6: 2, 7: 1}


def test_clave_de_correccion(base):
    clave = {f"K{i}": c for i, c in enumerate("VFFVFVVFVV", start=1)}
    for codigo, correcta in clave.items():
        assert db.session.get(Item, codigo).respuesta_correcta == correcta
    assert db.session.get(Item, "Q2").respuesta_correcta == "2"


def test_invertidos_y_descriptivos(base):
    invertidos = {i.codigo for i in Item.query.filter_by(invertido=True)}
    assert invertidos == {"A5", "B5", "B6"}
    assert not db.session.get(Item, "A6").suma_al_indice
    assert not db.session.get(Item, "B4").suma_al_indice


def test_edad_desde_18_y_situacion_laboral_v03(base):
    edades = [o.texto for o in db.session.get(Item, "D1").opciones]
    assert edades[0].startswith("18")
    d5 = db.session.get(Item, "D5")
    assert d5.tipo_respuesta == "multiple"
    assert [o.texto for o in d5.opciones] == ["Estudiante", "Empleado", "Monotributista", "No trabajo"]


def test_carreras_con_departamento(base):
    carreras = db.session.get(Item, "D3").opciones
    assert len(carreras) == 22
    assert all(o.grupo for o in carreras)


def test_ninguno_es_excluyente(base):
    excluyentes = Opcion.query.filter_by(excluyente=True).all()
    assert [(o.item_codigo, o.texto) for o in excluyentes] == [("E1", "Ninguno")]


def test_carga_es_repetible(base):
    assert cargar_catalogo() == (40, 212)
    sembrar_base()
    assert Origen.query.count() == 4
    assert Configuracion.query.count() == 1


def test_cierre_16_11_hora_argentina(base):
    cierre = db.session.get(Configuracion, 1).fecha_cierre
    assert cierre.replace(tzinfo=FECHA_CIERRE.tzinfo) == FECHA_CIERRE
    assert db.session.get(Configuracion, 1).encuesta_abierta is False


def _respuesta():
    r = Respuesta(origen=Origen.query.filter_by(codigo="directo").one(), version_consentimiento="1.0",
                  token_navegador=uuid.uuid4())
    db.session.add(r)
    db.session.flush()
    return r


def test_catalogo_congelado_con_respuestas(base):
    _respuesta()
    db.session.commit()
    with pytest.raises(RuntimeError):
        cargar_catalogo()


def test_detalle_exige_opcion_o_texto(base):
    r = _respuesta()
    db.session.add(DetalleRespuesta(respuesta_id=r.id, item_codigo="P1"))
    with pytest.raises(IntegrityError):
        db.session.commit()


def test_json_fuente_coincide_con_v03():
    datos = leer_catalogo()
    assert datos["version"] == "v03"
    assert len(datos["items"]) == 40
