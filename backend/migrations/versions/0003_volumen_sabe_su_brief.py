"""Un volumen sabe de que brief es.

SPEC-003, fase E. Sin esta columna, la lectura no puede responder «quien es el
destinatario de esta novela»: la consulta acababa adivinandolo por parecido del titulo,
que funciona en una demo y falla en cuanto hay dos novelas para dos Martas distintas.

Nullable a proposito: los volumenes que ya existan no tienen brief conocido, y ponerles
uno inventado seria peor que dejar el hueco a la vista.

Revision ID: 0003
"""

from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE volumen ADD COLUMN brief_id TEXT REFERENCES brief(id)")
    op.execute("CREATE INDEX idx_volumen_por_brief ON volumen(brief_id)")


def downgrade() -> None:
    """No hay marcha atras: las migraciones son hacia delante (RF-STO-02)."""
    raise NotImplementedError(
        "Las migraciones de este proyecto son hacia delante. Para volver atras, "
        "reconstruye la base desde cero."
    )
