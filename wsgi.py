"""Punto de entrada de la aplicación.

Lo usan Gunicorn en el servidor (``gunicorn wsgi:app``) y los comandos de
Flask (``flask --app wsgi ...``). Antes de crear la aplicación se cargan las
variables del archivo ``.env``, si existe, para el trabajo en una computadora
local.
"""
from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402  (tiene que ir después de load_dotenv)

app = create_app()
