"""Modelo físico de la base (9 tablas). No se guardan datos personales ni direcciones IP."""
import uuid
from datetime import datetime, timezone

from . import db


def ahora_utc():
    return datetime.now(timezone.utc)


class Origen(db.Model):
    __tablename__ = "origen"
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)  # qr, whatsapp, facebook, directo
    nombre = db.Column(db.String(50), nullable=False)


class Item(db.Model):
    """Una pregunta del cuestionario (catálogo cargado desde data/cuestionario_v03.json)."""
    __tablename__ = "item"
    codigo = db.Column(db.String(10), primary_key=True)  # D1, Q1, K1, A1, B1, E1, P1...
    seccion = db.Column(db.SmallInteger, nullable=False)
    orden = db.Column(db.SmallInteger, nullable=False)
    texto = db.Column(db.Text, nullable=False)
    tipo_respuesta = db.Column(db.String(15), nullable=False)
    obligatorio = db.Column(db.Boolean, nullable=False, default=True)
    invertido = db.Column(db.Boolean, nullable=False, default=False)
    suma_al_indice = db.Column(db.Boolean, nullable=False, default=False)
    respuesta_correcta = db.Column(db.String(10))
    opciones = db.relationship("Opcion", back_populates="item", order_by="Opcion.orden",
                               cascade="all, delete-orphan")

    __table_args__ = (
        db.CheckConstraint(
            "tipo_respuesta IN ('unica','multiple','desplegable','vf','likert','frecuencia','abierta')",
            name="ck_item_tipo"),
    )


class Opcion(db.Model):
    __tablename__ = "opcion"
    id = db.Column(db.Integer, primary_key=True)
    item_codigo = db.Column(db.String(10), db.ForeignKey("item.codigo"), nullable=False)
    codigo = db.Column(db.String(10), nullable=False)
    texto = db.Column(db.Text, nullable=False)
    orden = db.Column(db.SmallInteger, nullable=False)
    grupo = db.Column(db.String(120))  # departamento, en D3
    excluyente = db.Column(db.Boolean, nullable=False, default=False)  # "Ninguno" en E1
    item = db.relationship("Item", back_populates="opciones")

    __table_args__ = (db.UniqueConstraint("item_codigo", "codigo", name="uq_opcion_item_codigo"),)


class Respuesta(db.Model):
    """Una participación. Se crea al aceptar el consentimiento; enviada_en queda vacía si abandona."""
    __tablename__ = "respuesta"
    id = db.Column(db.Integer, primary_key=True)
    origen_id = db.Column(db.Integer, db.ForeignKey("origen.id"), nullable=False)
    desde_qr = db.Column(db.Boolean, nullable=False, default=False)
    token_navegador = db.Column(db.Uuid, unique=True, nullable=False, default=uuid.uuid4)
    version_consentimiento = db.Column(db.String(10), nullable=False)
    iniciada_en = db.Column(db.DateTime(timezone=True), nullable=False, default=ahora_utc)
    enviada_en = db.Column(db.DateTime(timezone=True))
    origen = db.relationship("Origen")
    detalles = db.relationship("DetalleRespuesta", back_populates="respuesta",
                               cascade="all, delete-orphan")


class DetalleRespuesta(db.Model):
    """Una opción elegida (o el texto libre de P1). Las preguntas múltiples generan una fila por opción."""
    __tablename__ = "detalle_respuesta"
    id = db.Column(db.Integer, primary_key=True)
    respuesta_id = db.Column(db.Integer, db.ForeignKey("respuesta.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    item_codigo = db.Column(db.String(10), db.ForeignKey("item.codigo"), nullable=False)
    opcion_id = db.Column(db.Integer, db.ForeignKey("opcion.id"))
    texto_libre = db.Column(db.Text)
    respuesta = db.relationship("Respuesta", back_populates="detalles")
    opcion = db.relationship("Opcion")

    __table_args__ = (
        db.CheckConstraint("(opcion_id IS NOT NULL) <> (texto_libre IS NOT NULL)", name="ck_detalle_valor"),
        db.UniqueConstraint("respuesta_id", "item_codigo", "opcion_id", name="uq_detalle"),
    )


class Rechazo(db.Model):
    """Alguien que no aceptó el consentimiento o declaró ser menor de 18. No se guarda nada más."""
    __tablename__ = "rechazo"
    id = db.Column(db.Integer, primary_key=True)
    motivo = db.Column(db.String(15), nullable=False)
    origen_id = db.Column(db.Integer, db.ForeignKey("origen.id"), nullable=False)
    fecha_hora = db.Column(db.DateTime(timezone=True), nullable=False, default=ahora_utc)
    origen = db.relationship("Origen")

    __table_args__ = (db.CheckConstraint("motivo IN ('no_acepta','menor')", name="ck_rechazo_motivo"),)


class VisitaQR(db.Model):
    """Un ingreso a la página del QR. token_visitante permite contar visitantes únicos."""
    __tablename__ = "visita_qr"
    id = db.Column(db.Integer, primary_key=True)
    fecha_hora = db.Column(db.DateTime(timezone=True), nullable=False, default=ahora_utc, index=True)
    token_visitante = db.Column(db.Uuid, nullable=False, index=True)


class Configuracion(db.Model):
    """Una sola fila (id = 1) con el estado de la encuesta."""
    __tablename__ = "configuracion"
    id = db.Column(db.Integer, primary_key=True)
    fecha_publicacion = db.Column(db.DateTime(timezone=True))
    fecha_cierre = db.Column(db.DateTime(timezone=True), nullable=False)
    encuesta_abierta = db.Column(db.Boolean, nullable=False, default=False)
    version_consentimiento = db.Column(db.String(10), nullable=False, default="1.0")

    __table_args__ = (db.CheckConstraint("id = 1", name="ck_configuracion_unica"),)


class UsuarioAdmin(db.Model):
    __tablename__ = "usuario_admin"
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), unique=True, nullable=False)
    hash_clave = db.Column(db.String(255), nullable=False)
    intentos_fallidos = db.Column(db.SmallInteger, nullable=False, default=0)
    bloqueado_hasta = db.Column(db.DateTime(timezone=True))
