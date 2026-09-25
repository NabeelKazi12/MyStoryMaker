"""El nombre de un personaje se cambia, y el canon lo registra.

SPEC-013, fase A. `canon_cambio.operacion` admite `renombrar`: el cambio de nombre es un
evento de canon con el valor anterior y el nuevo en `datos`, no una edicion en sitio sin
revision (RF-NOM-12).

SQLite no altera un `CHECK`, asi que la tabla se reconstruye: se crea con la restriccion
nueva, se copian las filas con sus ids -la reconstruccion del canon depende de su orden- y
se sustituye a la anterior.

Revision ID: 0009
"""

from __future__ import annotations

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


DECISION_DE_SPEC_013 = (
    "rd-d26",
    "El cambio de nombre de un personaje es una sustitucion exacta en canon, esqueleto, "
    "resumenes y prosa, con revision de canon, borrador nuevo por escena y version nueva",
    "Regenerar con el Redactor los capitulos donde aparece el personaje; cambiar solo la "
    "ficha del personaje",
    "Regenerar cuesta invocaciones y reescribe lo que nadie pidio cambiar. Cambiar solo la "
    "ficha deja canon fantasma: los resumenes y la prosa siguen con el nombre viejo y el "
    "capitulo siguiente lo recupera",
    "orchestrator",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE canon_cambio_nueva (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            revision INTEGER NOT NULL REFERENCES canon_revision(revision),
            tabla TEXT NOT NULL,
            fila_id TEXT NOT NULL,
            operacion TEXT NOT NULL
                CHECK (operacion IN ('insertar', 'cerrar_intervalo', 'renombrar')),
            datos TEXT NOT NULL DEFAULT ''
        )
        """
    )
    op.execute(
        "INSERT INTO canon_cambio_nueva (id, revision, tabla, fila_id, operacion, datos) "
        "SELECT id, revision, tabla, fila_id, operacion, datos FROM canon_cambio"
    )
    op.execute("DROP TABLE canon_cambio")
    op.execute("ALTER TABLE canon_cambio_nueva RENAME TO canon_cambio")

    identificador, decision, alternativas, motivo, ambito = DECISION_DE_SPEC_013
    op.execute(
        "INSERT INTO registro_decision "
        "(id, decision, alternativas, motivo, ambito, reversible, tomada_en) VALUES "
        f"('{identificador}', '{decision}', '{alternativas}', '{motivo}', "
        f"'{ambito}', 1, datetime('now'))"
    )


def downgrade() -> None:
    """No hay marcha atras: las migraciones son hacia delante (RF-STO-02)."""
    raise NotImplementedError("las migraciones de MyStoryMaker no se deshacen")
