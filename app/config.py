"""Configuración de la aplicación.

Los datos sensibles (clave secreta y cadena de conexión a la base) no están en
el código: se leen de variables de entorno. En el servidor se cargan en el
panel de Render; en una computadora local, en un archivo ``.env`` (ver
``.env.example``).
"""
import os


def _normalizar_url(url: str) -> str:
    """Adapta la cadena de conexión al formato que espera SQLAlchemy.

    Neon (el servicio de PostgreSQL) entrega direcciones que empiezan con
    ``postgresql://`` o ``postgres://``. SQLAlchemy necesita que se indique el
    controlador a usar, en este caso psycopg 3: ``postgresql+psycopg://``.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Config:
    """Configuración de producción."""

    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = _normalizar_url(os.environ.get("DATABASE_URL", ""))
    # Neon suspende la base tras 5 minutos sin uso: se verifica la conexión antes de usarla.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}
    # La cookie de sesión solo viaja por HTTPS, no es accesible desde JavaScript
    # y no se envía en pedidos que se originan en otros sitios.
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PREFERRED_URL_SCHEME = "https"


class TestConfig(Config):
    """Configuración para las pruebas automáticas (pytest).

    Usa una base SQLite en memoria, que se crea y se descarta en cada prueba,
    y desactiva lo que solo tiene sentido en el servidor (HTTPS y token CSRF).
    """

    TESTING = True
    SECRET_KEY = "clave-de-pruebas"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False
