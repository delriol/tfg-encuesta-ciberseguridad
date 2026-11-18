"""Configuración común de las pruebas: una aplicación con base SQLite en memoria."""
import pytest

from app import create_app, db


@pytest.fixture
def app():
    """Aplicación de prueba con las tablas creadas; se borran al terminar."""
    app = create_app("app.config.TestConfig")
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Cliente HTTP simulado para hacer pedidos a la aplicación."""
    return app.test_client()
