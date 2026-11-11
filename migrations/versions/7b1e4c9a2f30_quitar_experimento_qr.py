"""quitar experimento QR

El experimento con código QR no se realizó: se borran la tabla de visitas,
la columna desde_qr y el origen "qr" (solo si ninguna respuesta lo usa).

Revision ID: 7b1e4c9a2f30
Revises: d02610c5b754
Create Date: 2026-11-11 03:30:00

"""
from alembic import op
import sqlalchemy as sa


revision = '7b1e4c9a2f30'
down_revision = 'd02610c5b754'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('visita_qr', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_visita_qr_token_visitante'))
        batch_op.drop_index(batch_op.f('ix_visita_qr_fecha_hora'))
    op.drop_table('visita_qr')

    with op.batch_alter_table('respuesta', schema=None) as batch_op:
        batch_op.drop_column('desde_qr')

    # Si alguna respuesta o rechazo quedó con origen "qr", la fila se conserva para no perder datos.
    op.execute(
        "DELETE FROM origen WHERE codigo = 'qr' "
        "AND NOT EXISTS (SELECT 1 FROM respuesta WHERE respuesta.origen_id = origen.id) "
        "AND NOT EXISTS (SELECT 1 FROM rechazo WHERE rechazo.origen_id = origen.id)"
    )


def downgrade():
    op.execute(
        "INSERT INTO origen (codigo, nombre) SELECT 'qr', 'Código QR de los carteles' "
        "WHERE NOT EXISTS (SELECT 1 FROM origen WHERE codigo = 'qr')"
    )

    with op.batch_alter_table('respuesta', schema=None) as batch_op:
        batch_op.add_column(sa.Column('desde_qr', sa.Boolean(), nullable=False,
                                      server_default=sa.false()))
    op.execute("UPDATE respuesta SET desde_qr = (origen_id IN (SELECT id FROM origen WHERE codigo = 'qr'))")

    op.create_table('visita_qr',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('fecha_hora', sa.DateTime(timezone=True), nullable=False),
    sa.Column('token_visitante', sa.Uuid(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('visita_qr', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_visita_qr_fecha_hora'), ['fecha_hora'], unique=False)
        batch_op.create_index(batch_op.f('ix_visita_qr_token_visitante'), ['token_visitante'], unique=False)
