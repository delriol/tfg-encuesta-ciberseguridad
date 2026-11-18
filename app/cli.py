"""Comandos de consola propios del sistema.

Se ejecutan con ``flask --app wsgi <comando>``:

- preparar-base: carga los datos iniciales y el cuestionario. Render lo corre
  en cada despliegue, después de aplicar las migraciones.
- crear-admin USUARIO: crea el usuario del panel del investigador o le cambia
  la clave.
"""
import getpass

import click
from werkzeug.security import generate_password_hash

from . import db
from .catalogo import cargar_catalogo, sembrar_base
from .models import UsuarioAdmin


def registrar_comandos(app):
    """Agrega los comandos de este módulo a la aplicación."""
    @app.cli.command("preparar-base")
    def preparar_base():
        """Carga orígenes, configuración y el cuestionario.

        Si ya hay respuestas guardadas, el cuestionario no se modifica (así no
        cambian las preguntas en medio de la recolección) y el despliegue sigue.
        """
        sembrar_base()
        try:
            items, opciones = cargar_catalogo()
        except RuntimeError as e:
            click.echo(f"Catálogo sin cambios: {e}")
            return
        click.echo(f"Base lista: {items} preguntas y {opciones} opciones.")

    @app.cli.command("crear-admin")
    @click.argument("usuario")
    def crear_admin(usuario):
        """Crea o cambia la clave del usuario del panel.

        La clave se pide por teclado sin mostrarla, se exige un mínimo de 12
        caracteres y se guarda solo su hash (nunca la clave en texto plano).
        También se desbloquea el usuario si estaba bloqueado por intentos fallidos.
        """
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
