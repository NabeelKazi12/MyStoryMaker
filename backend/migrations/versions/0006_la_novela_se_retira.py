"""Una novela se puede eliminar: se retira, no se borra.

SPEC-009, fase A. Una columna nullable, `volumen.eliminada_en`: vacia mientras la novela
existe, con fecha cuando se retira. Nada mas cambia en la base, y a proposito: borrar las
filas de una novela romperia tres reglas que el sistema hace cumplir —las versiones no se
pierden (`VersionAnteriorSeConserva`), las aprobaciones no se borran (trigger de `0005`) y
`audit_log` y `registro_decision` son inmutables—.

Revision ID: 0006
"""

from __future__ import annotations

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


# La decision de SPEC-009, en la base por lo mismo que las anteriores (`CLAUDE.md` 8).
DECISION_DE_SPEC_009 = (
    "rd-d23",
    "Eliminar una novela la retira con fecha: desaparece de la biblioteca y de la API y "
    "sus filas se conservan",
    "Borrado en cascada de capitulos, escenas, borradores, canon, versiones y tareas",
    "El borrado rompe VersionAnteriorSeConserva, el trigger que impide borrar "
    "aprobaciones y la inmutabilidad de audit_log. Retirar da lo que se pedia -que la "
    "novela deje de verse- sin derogar nada. Restaurar es poner eliminada_en a NULL en la "
    "base; la interfaz no lo ofrece",
    "api",
)


def upgrade() -> None:
    op.execute("ALTER TABLE volumen ADD COLUMN eliminada_en TEXT")

    identificador, decision, alternativas, motivo, ambito = DECISION_DE_SPEC_009
    op.execute(
        "INSERT INTO registro_decision "
        "(id, decision, alternativas, motivo, ambito, reversible, tomada_en) VALUES "
        f"('{identificador}', '{decision}', '{alternativas}', '{motivo}', "
        f"'{ambito}', 1, datetime('now'))"
    )


def downgrade() -> None:
    """No hay marcha atras: las migraciones son hacia delante (RF-STO-02)."""
    raise NotImplementedError("las migraciones de MyStoryMaker no se deshacen")
