import getpass

import click
from werkzeug.security import generate_password_hash

from . import db
from .catalogo import cargar_catalogo, sembrar_base
from .models import UsuarioAdmin


def registrar_comandos(app):
    @app.cli.command("preparar-base")
    def preparar_base():
        """Carga orígenes, configuración y el cuestionario."""
        sembrar_base()
        try:
            items, opciones = cargar_catalogo()
        except RuntimeError as e:
            # Con la encuesta en marcha el catálogo queda congelado; el deploy sigue.
            click.echo(f"Catálogo sin cambios: {e}")
            return
        click.echo(f"Base lista: {items} preguntas y {opciones} opciones.")

    @app.cli.command("crear-admin")
    @click.argument("usuario")
    def crear_admin(usuario):
        """Crea o cambia la clave del usuario del panel."""
        clave = getpass.getpass("Clave (mínimo 12 caracteres): ")
        if len(clave) < 12:
            raise click.ClickException("La clave debe tener al menos 12 caracteres.")
        if clave != getpass.getpass("Repetir clave: "):
            raise click.ClickException("Las claves no coinciden.")
        u = UsuarioAdmin.query.filter_by(usuario=usuario).first() or UsuarioAdmin(usuario=usuario)
        u.hash_clave = generate_password_hash(clave)
        u.intentos_fallidos = 0
        u.bloqueado_hasta = None
        db.session.add(u)
        db.session.commit()
        click.echo(f"Usuario {usuario} listo.")
