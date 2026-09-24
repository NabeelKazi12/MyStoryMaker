"""La procedencia cuenta los tokens de cada llamada.

SPEC-012, fase A. Dos columnas nullable en `procedencia`: los tokens de entrada y de
salida que devuelve el cliente del modelo. Llegaban en cada respuesta y se perdian entre
el cliente y la base, asi que el coste de una novela se podia sumar pero no explicar.

Nullable a proposito: las llamadas anteriores no los guardaron, y rellenarlas con una
estimacion seria inventar un dato. La pestaña de gastos las cuenta aparte (N-05).

Revision ID: 0007
"""

from __future__ import annotations

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


DECISION_DE_SPEC_010 = (
    "rd-d24",
    "Cada llamada al modelo es una traza de Langfuse con el id de su procedencia, en la "
    "sesion de su novela; los gastos se leen de SQLite",
    "Una traza por novela con un span por llamada; leer los gastos de Langfuse",
    "Con el id de la procedencia como id de traza, cada fila de la pestaña de gastos "
    "enlaza a su llamada sin guardar ningun id nuevo, y la novela entera se ve junta como "
    "sesion. Leer de Langfuse haria depender la pestaña de un servicio externo, contra "
    "SPEC-003 S-02",
    "observability",
)


def upgrade() -> None:
    op.execute("ALTER TABLE procedencia ADD COLUMN tokens_entrada INTEGER")
    op.execute("ALTER TABLE procedencia ADD COLUMN tokens_salida INTEGER")

    identificador, decision, alternativas, motivo, ambito = DECISION_DE_SPEC_010
    op.execute(
        "INSERT INTO registro_decision "
        "(id, decision, alternativas, motivo, ambito, reversible, tomada_en) VALUES "
        f"('{identificador}', '{decision}', '{alternativas}', '{motivo}', "
        f"'{ambito}', 1, datetime('now'))"
    )


def downgrade() -> None:
    """No hay marcha atras: las migraciones son hacia delante (RF-STO-02)."""
    raise NotImplementedError("las migraciones de MyStoryMaker no se deshacen")
