"""La novela se aprueba: la firma de una persona cierra el volumen.

SPEC-007, fase A. Una tabla, y dos reglas que la base hace cumplir por si misma en lugar
de confiar en que el codigo las respete:

- **Ninguna aprobacion se borra.** Reabrir la novela marca `retirada_en`; la fila se
  queda. Un trigger rechaza el `DELETE`: una aprobacion que desaparece no deja rastro de
  que alguien firmo una version, que es justo lo que la tabla existe para recordar.
- **Una sola vigente por volumen.** Un indice unico parcial sobre las no retiradas. Dos
  aprobaciones vigentes a la vez harian ambigua la pregunta «¿sobre que version se
  firmo?».

Revision ID: 0005
"""

from __future__ import annotations

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


# La decision de SPEC-007, en la base por lo mismo que las de SPEC-004 (`0004`): un
# `RegistroDeDecision` es inmutable y no se borra (`CLAUDE.md` 8).
DECISION_DE_SPEC_007 = (
    "rd-d22",
    "La firma humana es la evidencia de promesa al lector en la puerta Volumen cerrado",
    "Aceptar por excepcion autorizada cada borrador al aprobar la novela; dejar la "
    "aprobacion como una marca que no toca ninguna puerta",
    "verification.md asigna promesa al lector a una persona, y es la unica evidencia "
    "ausente de Volumen cerrado en v1. Aceptar los borradores saltaria Escena limpia, que "
    "es el riesgo F-06; una marca suelta dejaria la puerta sin evaluar para siempre. Lo "
    "determinista de la puerta sigue bloqueando aunque haya firma",
    "orchestrator",
)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE aprobacion_de_volumen (
            id TEXT PRIMARY KEY,
            volumen_id TEXT NOT NULL REFERENCES volumen(id),
            version_id TEXT NOT NULL REFERENCES version_novela(id),
            aprobada_en TEXT NOT NULL,
            retirada_en TEXT
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX idx_aprobacion_vigente ON aprobacion_de_volumen(volumen_id) "
        "WHERE retirada_en IS NULL"
    )
    op.execute(
        """
        CREATE TRIGGER aprobacion_de_volumen_no_se_borra
        BEFORE DELETE ON aprobacion_de_volumen
        BEGIN
            SELECT RAISE(ABORT, 'una aprobacion no se borra: se retira');
        END
        """
    )

    identificador, decision, alternativas, motivo, ambito = DECISION_DE_SPEC_007
    op.execute(
        "INSERT INTO registro_decision "
        "(id, decision, alternativas, motivo, ambito, reversible, tomada_en) VALUES "
        f"('{identificador}', '{decision}', '{alternativas}', '{motivo}', "
        f"'{ambito}', 1, datetime('now'))"
    )


def downgrade() -> None:
    """No hay marcha atras: las migraciones son hacia delante (RF-STO-02)."""
    raise NotImplementedError("las migraciones de MyStoryMaker no se deshacen")
