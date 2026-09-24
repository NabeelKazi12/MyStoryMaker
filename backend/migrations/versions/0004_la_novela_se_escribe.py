"""El capitulo tiene titulo y el plan sabe que novela escribe.

SPEC-004, fase A. Dos columnas, y las dos existen por la misma razon: sin ellas la
escritura de una novela no se puede consultar por la novela.

- `capitulo.titulo`: el Planner reparte la novela en capitulos con nombre, y la lectura
  los tiene que enseniar. Sin la columna, el titulo se perderia entre la salida del rol y
  la base, y la pantalla acabaria inventando «Capitulo 3» para todo.
- `plan.volumen_id`: sin el, «como va la escritura de esta novela» solo se puede responder
  adivinando por el prefijo del identificador de la tarea. Funciona con una novela en la
  base y falla en cuanto hay dos.

Las dos son nullable a proposito: los planes y capitulos que ya existan no tienen ni
titulo ni volumen conocido, y rellenarlos con algo inventado seria peor que dejar el hueco
a la vista.

Revision ID: 0004
"""

from __future__ import annotations

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


# Las dos decisiones de SPEC-004 6.3. Van en la migracion y no solo en la spec porque un
# `RegistroDeDecision` vive en la base, es inmutable y no se borra (`CLAUDE.md` 8): en obras
# largas la deriva rara vez viene de mala prosa, viene de decisiones olvidadas y luego
# contradichas sin que nadie se de cuenta.
DECISIONES_DE_SPEC_004 = (
    (
        "rd-d20",
        "El modo de demostracion existe, es explicito y se declara en la Procedencia",
        "Caer en prosa fabricada cuando no hay credencial; no tener modo de demostracion "
        "y dejar el recorrido inobservable hasta que haya clave",
        "Un sistema que baja de modelo en silencio produce una novela que nadie sabe que "
        "no es del modelo, que es lo que D-08 prohibe. Pedirlo por su nombre y marcarlo "
        "en la columna que siempre se mira conserva la distincion para siempre",
        "worker",
    ),
    (
        "rd-d21",
        "La lectura sirve el borrador no aceptado, marcado como tal y con el motivo",
        "Esperar a que la puerta escena_limpia lo acepte antes de mostrarlo",
        "En v1 esa puerta siempre trae evidencia ausente, asi que esperar es esperar para "
        "siempre y la lectura queda vacia sin que nada lo explique. Mostrarlo con su "
        "estado no convierte la ausencia de evidencia en evidencia favorable",
        "api",
    ),
)


def upgrade() -> None:
    op.execute("ALTER TABLE capitulo ADD COLUMN titulo TEXT NOT NULL DEFAULT ''")
    op.execute("ALTER TABLE plan ADD COLUMN volumen_id TEXT REFERENCES volumen(id)")
    # El modo con el que se encargo la escritura. Lo fija quien pide la escritura y lo lee
    # el worker; guardarlo en el plan es lo que impide que una novela empezada con el
    # modelo termine en demostracion porque entretanto se cayo la credencial.
    op.execute(
        "ALTER TABLE plan ADD COLUMN modo TEXT NOT NULL DEFAULT 'modelo' "
        "CHECK (modo IN ('modelo', 'demostracion'))"
    )
    op.execute("CREATE INDEX idx_plan_por_volumen ON plan(volumen_id)")

    for identificador, decision, alternativas, motivo, ambito in DECISIONES_DE_SPEC_004:
        op.execute(
            "INSERT INTO registro_decision "
            "(id, decision, alternativas, motivo, ambito, reversible, tomada_en) VALUES "
            f"('{identificador}', '{decision}', '{alternativas}', '{motivo}', "
            f"'{ambito}', 1, datetime('now'))"
        )


def downgrade() -> None:
    """No hay marcha atras: las migraciones son hacia delante (RF-STO-02)."""
    raise NotImplementedError(
        "Las migraciones de este proyecto son hacia delante. Para volver atras, "
        "reconstruye la base desde cero."
    )
