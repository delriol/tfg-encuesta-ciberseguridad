"""Creación y configuración de la aplicación web de la encuesta.

La aplicación sigue el patrón *application factory* de Flask: la función
``create_app`` arma una instancia nueva con su configuración, la base de datos,
la protección CSRF de los formularios, los comandos de consola y las dos partes
del sistema (la encuesta pública y el panel del investigador).
"""
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text
from werkzeug.middleware.proxy_fix import ProxyFix

# Extensiones compartidas por todo el sistema. Se crean acá sin aplicación
# y se asocian a ella dentro de create_app().
db = SQLAlchemy()        # acceso a la base de datos (ORM)
migrate = Migrate()      # migraciones del esquema (carpeta migrations/)
csrf = CSRFProtect()     # token anti-CSRF en todos los formularios POST


def create_app(config_object="app.config.Config"):
    """Crea la aplicación Flask lista para usar.

    config_object: clase de configuración a cargar. En producción es
    ``Config``; las pruebas automáticas usan ``TestConfig``.

    Si falta alguna variable de entorno obligatoria se corta el arranque con un
    mensaje claro, en lugar de fallar más tarde con un error difícil de entender.
    """
    app = Flask(__name__)
    app.config.from_object(config_object)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("Falta la variable de entorno SECRET_KEY")
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError("Falta la variable de entorno DATABASE_URL")

    # Render atiende detrás de un proxy: así la app sabe que la conexión original es HTTPS.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    from . import models  # noqa: F401  (registra las tablas)
    from .cli import registrar_comandos

    registrar_comandos(app)

    from .encuesta import bp as encuesta_bp

    app.register_blueprint(encuesta_bp)

    from .panel import bp as panel_bp

    app.register_blueprint(panel_bp)

    @app.after_request
    def cabeceras_de_seguridad(resp):
        """Agrega cabeceras HTTP de seguridad a todas las respuestas.

        - HSTS: el navegador usa siempre HTTPS con este sitio.
        - nosniff: el navegador no adivina el tipo de los archivos.
        - X-Frame-Options y frame-ancestors: la web no se puede incrustar en
          otra página (protege contra el *clickjacking*).
        - Referrer-Policy: no se informa a sitios externos desde qué página se llegó.
        - Content-Security-Policy: solo se cargan estilos, scripts e imágenes
          del propio sitio.
        """
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; form-action 'self'",
        )
        return resp

    @app.get("/salud")
    def salud():
        """Chequeo de funcionamiento para el monitoreo externo.

        Lo consultan Render y UptimeRobot (cada 5 minutos). Responde 200 solo si
        la base de datos contesta; si no, 503, y el monitoreo envía un aviso.
        """
        try:
            db.session.execute(text("SELECT 1"))
            return {"estado": "ok"}, 200
        except Exception:
            db.session.rollback()
            return {"estado": "sin base de datos"}, 503

    return app
