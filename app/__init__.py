from flask import Flask, render_template
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()


def create_app(config_object="app.config.Config"):
    app = Flask(__name__)
    app.config.from_object(config_object)
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("Falta la variable de entorno SECRET_KEY")
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError("Falta la variable de entorno DATABASE_URL")

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    from . import models  # noqa: F401  (registra las tablas)
    from .cli import registrar_comandos

    registrar_comandos(app)

    @app.after_request
    def cabeceras_de_seguridad(resp):
        resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' https://cdn.jsdelivr.net; "
            "script-src 'self' https://cdn.jsdelivr.net; img-src 'self' data:; frame-ancestors 'none'",
        )
        return resp

    @app.get("/")
    def inicio():
        return render_template("en_construccion.html")

    @app.get("/salud")
    def salud():
        # Lo consulta UptimeRobot cada 5 minutos: responde 200 solo si la base contesta.
        try:
            db.session.execute(text("SELECT 1"))
            return {"estado": "ok"}, 200
        except Exception:
            db.session.rollback()
            return {"estado": "sin base de datos"}, 503

    return app
