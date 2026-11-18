"""Configuración de Alembic para ejecutar las migraciones con Flask-Migrate.

Archivo estándar generado por Flask-Migrate; toma la conexión a la base de la
configuración de la aplicación Flask.
"""
import logging
from logging.config import fileConfig

from flask import current_app

from alembic import context

# Objeto de configuración de Alembic (valores de alembic.ini).
config = context.config

# Configura los mensajes de registro (logging) según alembic.ini.
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')


def get_engine():
    """Motor de base de datos de la aplicación Flask."""
    try:
        # Flask-SQLAlchemy < 3
        return current_app.extensions['migrate'].db.get_engine()
    except (TypeError, AttributeError):
        # Flask-SQLAlchemy >= 3
        return current_app.extensions['migrate'].db.engine


def get_engine_url():
    """Cadena de conexión de la aplicación, con % escapado para el archivo .ini."""
    try:
        return get_engine().url.render_as_string(hide_password=False).replace(
            '%', '%%')
    except AttributeError:
        return str(get_engine().url).replace('%', '%%')


# Se usan los modelos de la aplicación para comparar y generar migraciones.
config.set_main_option('sqlalchemy.url', get_engine_url())
target_db = current_app.extensions['migrate'].db


def get_metadata():
    """Metadatos de las tablas definidas en app/models.py."""
    if hasattr(target_db, 'metadatas'):
        return target_db.metadatas[None]
    return target_db.metadata


def run_migrations_offline():
    """Modo "offline": genera el SQL de las migraciones sin conectarse a la base."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=get_metadata(), literal_binds=True
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Modo "online": se conecta a la base y aplica las migraciones."""

    # Evita crear una migración vacía cuando no hubo cambios en los modelos.
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No hay cambios en el esquema.')

    conf_args = current_app.extensions['migrate'].configure_args
    if conf_args.get("process_revision_directives") is None:
        conf_args["process_revision_directives"] = process_revision_directives

    connectable = get_engine()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            **conf_args
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
