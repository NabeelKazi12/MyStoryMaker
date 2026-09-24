"""Los personajes se declaran en el encargo.

SPEC-011, fase A. Una tabla de la capa de especificacion, colgada del `brief` como el
destinatario: lo que quien encarga dice de los personajes antes de que exista la novela.
No es canon —el canon lo abre el Planner—, y por eso no comparte tabla con `personaje`:
un declarado que el Planner todavia no ha propuesto no es un hecho de la historia.

`es_destinatario` marca a la persona a quien va dedicada; un indice unico parcial impide
que haya dos en el mismo encargo (RF-PER-02).

Revision ID: 0008
"""

from __future__ import annotations

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


DECISION_DE_SPEC_011 = (
    "rd-d25",
    "Los personajes se declaran en el encargo y la apertura los cobra: tiene que proponerlos "
    "todos con su nombre y su papel o el plan se rechaza entero",
    "Escribirlos en el canon al cerrar la entrevista; dejarlos como sugerencia en el prompt",
    "Escribirlos en el canon saltaria la apertura y haria del encargo una canonizacion, "
    "contra AGENTS.md 1.5. Dejarlos como sugerencia es lo que ya pasaba con la destinataria: "
    "el prompt lo pedia y nada lo comprobaba. Cobrarlos en la apertura es el mismo patron "
    "que los recuerdos obligatorios",
    "orchestrator",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE personaje_declarado (
            id TEXT PRIMARY KEY,
            brief_id TEXT NOT NULL REFERENCES brief(id),
            orden INTEGER NOT NULL,
            nombre TEXT NOT NULL CHECK (trim(nombre) <> ''),
            papel TEXT NOT NULL CHECK (papel IN ('protagonico', 'secundario', 'ambiental')),
            relacion TEXT NOT NULL DEFAULT '',
            descripcion TEXT NOT NULL DEFAULT '',
            es_destinatario INTEGER NOT NULL DEFAULT 0 CHECK (es_destinatario IN (0, 1)),
            UNIQUE (brief_id, orden)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX idx_una_destinataria_por_encargo "
        "ON personaje_declarado(brief_id) WHERE es_destinatario = 1"
    )

    identificador, decision, alternativas, motivo, ambito = DECISION_DE_SPEC_011
    op.execute(
        "INSERT INTO registro_decision "
        "(id, decision, alternativas, motivo, ambito, reversible, tomada_en) VALUES "
        f"('{identificador}', '{decision}', '{alternativas}', '{motivo}', "
        f"'{ambito}', 1, datetime('now'))"
    )


def downgrade() -> None:
    """No hay marcha atras: las migraciones son hacia delante (RF-STO-02)."""
    raise NotImplementedError("las migraciones de MyStoryMaker no se deshacen")
