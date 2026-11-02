import os


def _normalizar_url(url: str) -> str:
    """Neon entrega postgresql://; SQLAlchemy necesita el driver psycopg 3."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = _normalizar_url(os.environ.get("DATABASE_URL", ""))
    # Neon suspende la base tras 5 minutos sin uso: se verifica la conexión antes de usarla.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PREFERRED_URL_SCHEME = "https"


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "clave-de-pruebas"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False
