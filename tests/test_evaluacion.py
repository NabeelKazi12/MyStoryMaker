"""La bateria de cinco briefs y la tabla de que validador cazo que.

SPEC-003, fase G, pasos G-01 y G-02. Cubre RF-EVA-01 y RF-EVA-02.

La tabla de `docs/evaluacion.md` se **genera** de esta ejecucion, no se escribe a mano:
una tabla escrita a mano dice lo que su autor creia, no lo que paso.
"""

from __future__ import annotations

import sqlite3

import pytest

from backend.agents.entrevistador.entrevistador import (
    BriefIncompleto,
    construir_encargo,
    envolver_texto_no_confiable,
)
from backend.formal.lean import incoherencias_detectables
from backend.store.repositories import StoryBible
from tests.briefs import LOS_CINCO, BriefDePrueba


def _evaluar(brief: BriefDePrueba, conn: sqlite3.Connection) -> set[str]:
    """Corre los validadores que no necesitan invocar al modelo y devuelve lo que salto."""
    fallos: set[str] = set()

    try:
        construir_encargo(f"br-{brief.nombre}", brief.respuestas)
    except BriefIncompleto:
        fallos.add("entrevista_contradiccion")

    if brief.texto_libre:
        envuelto = envolver_texto_no_confiable(brief.texto_libre)
        if envuelto.intentos_de_injection:
            fallos.add("injection_detectada")

    for fila in brief.cronologia:
        conn.execute(
            "INSERT OR IGNORE INTO lugar (id, nombre_canonico) VALUES (?, ?)",
            (fila["lugar_id"], fila["lugar_id"]),
        )
        conn.execute(
            "INSERT OR IGNORE INTO personaje (id, nombre_canonico, anio_de_nacimiento) "
            "VALUES (?, ?, ?)",
            (fila["personaje_id"], fila["personaje_id"], fila["anio_de_nacimiento"]),
        )
        conn.execute(
            "INSERT OR IGNORE INTO evento "
            "(id, descripcion, posicion_en_historia, tipo, momento, lugar_id) "
            "VALUES (?, ?, 10, 'accion', ?, ?)",
            (fila["evento_id"], fila["evento_id"], fila["momento"], fila["lugar_id"]),
        )
        conn.execute(
            "INSERT OR IGNORE INTO evento_participante (evento_id, entidad_id, rol_en_evento) "
            "VALUES (?, ?, 'agente')",
            (fila["evento_id"], fila["personaje_id"]),
        )
    conn.commit()

    for problema in incoherencias_detectables(StoryBible(conn)):
        fallos.add(problema.tipo)

    return fallos


@pytest.mark.invariants
@pytest.mark.parametrize("brief", LOS_CINCO, ids=lambda b: b.nombre)
def test_cada_brief_falla_exactamente_donde_debe(
    brief: BriefDePrueba, conn: sqlite3.Connection
) -> None:
    """RF-EVA-01 y RF-EVA-02.

    Los dos sentidos importan. Que el adversarial salte demuestra que la defensa existe;
    que los sanos no salten demuestra que la defensa discrimina. Un detector que marca
    todo es indistinguible de uno roto.
    """
    saltaron = _evaluar(brief, conn)

    assert saltaron == set(brief.fallos_esperados), (
        f"brief «{brief.nombre}»: esperaba {sorted(brief.fallos_esperados)} y salto "
        f"{sorted(saltaron)}"
    )


@pytest.mark.invariants
def test_la_bateria_tiene_los_dos_casos_que_el_alcance_exige() -> None:
    """Uno adversarial con injection y uno con incoherencia temporal sembrada."""
    nombres = {b.nombre for b in LOS_CINCO}

    assert len(LOS_CINCO) == 5
    assert {"injection", "incoherencia_temporal"} <= nombres
    assert any(b.fallos_esperados == () for b in LOS_CINCO), (
        "sin al menos un encargo sano, la bateria no distingue un sistema estricto de uno roto"
    )


@pytest.mark.invariants
def test_el_texto_del_brief_adversarial_se_conserva_entero(
    conn: sqlite3.Connection,
) -> None:
    """La defensa no es censurar: es que el texto deje de poder leerse como instruccion.

    De ese texto salen los recuerdos que la novela tiene que contar; recortarlo perderia
    el encargo junto con el ataque.
    """
    adversarial = next(b for b in LOS_CINCO if b.nombre == "injection")

    envuelto = envolver_texto_no_confiable(adversarial.texto_libre)

    assert "Mi padre era ferroviario en Lisboa." in envuelto.texto
    assert envuelto.texto.startswith("<<<texto_no_confiable")
