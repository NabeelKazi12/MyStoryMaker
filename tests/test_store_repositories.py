"""Repositorios: grafo causal por CTE, catalogo de predicados y canon versionado.

Cubre RF-STO-05, RF-STO-07 y RF-STO-08.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from backend.domain.diegetic.canon import Hecho
from backend.domain.errors import ErrorDeDominio
from backend.store import database
from backend.store.repositories import CanonVersionado, CatalogoDePredicados, GrafoCausal

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """Una base migrada por test: los repositorios escriben y no deben contaminarse."""
    import os

    destino = tmp_path / "canon.db"
    resultado = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=RAIZ,
        env={**os.environ, "MYSTORYMAKER_DB": str(destino)},
        capture_output=True,
        text=True,
    )
    assert resultado.returncode == 0, resultado.stderr
    conexion = database.abrir(destino)
    try:
        yield conexion
    finally:
        conexion.close()


def _eventos(conn: sqlite3.Connection, *, posiciones: dict[str, int]) -> None:
    for id_evento, posicion in posiciones.items():
        conn.execute(
            "INSERT INTO evento (id, descripcion, posicion_en_historia, tipo) "
            "VALUES (?, ?, ?, 'accion')",
            (id_evento, f"evento {id_evento}", posicion),
        )


def _causa(conn: sqlite3.Connection, *pares: tuple[str, str]) -> None:
    conn.executemany("INSERT INTO evento_causa (causa_id, efecto_id) VALUES (?, ?)", pares)


# --- RF-STO-08: consultas transitivas con CTE recursiva ------------------------------


@pytest.mark.invariants
def test_alcanzables_recorre_el_grafo_en_profundidad(conn: sqlite3.Connection) -> None:
    """Una cadena de cinco saltos se resuelve en una consulta, no en cinco viajes."""
    _eventos(conn, posiciones={f"ev-{i}": i * 10 for i in range(1, 7)})
    _causa(conn, ("ev-1", "ev-2"), ("ev-2", "ev-3"), ("ev-3", "ev-4"), ("ev-4", "ev-5"))

    assert GrafoCausal(conn).alcanzables_desde("ev-1") == {"ev-2", "ev-3", "ev-4", "ev-5"}
    assert GrafoCausal(conn).alcanzables_desde("ev-6") == frozenset()


@pytest.mark.invariants
def test_detecta_un_ciclo_indirecto(conn: sqlite3.Connection) -> None:
    """El ciclo corto lo corta el dominio; el largo solo se ve recorriendo el grafo."""
    _eventos(conn, posiciones={"ev-1": 10, "ev-2": 20, "ev-3": 30})
    _causa(conn, ("ev-1", "ev-2"), ("ev-2", "ev-3"), ("ev-3", "ev-1"))

    assert set(GrafoCausal(conn).ciclos()) == {"ev-1", "ev-2", "ev-3"}


@pytest.mark.invariants
def test_un_grafo_aciclico_no_reporta_ciclos(conn: sqlite3.Connection) -> None:
    """Que no invente: es la mitad de la comprobacion que exige verification.md 7."""
    _eventos(conn, posiciones={"ev-1": 10, "ev-2": 20, "ev-3": 30})
    _causa(conn, ("ev-1", "ev-2"), ("ev-1", "ev-3"), ("ev-2", "ev-3"))

    assert GrafoCausal(conn).ciclos() == ()


@pytest.mark.invariants
def test_detecta_causa_posterior_a_su_efecto(conn: sqlite3.Connection) -> None:
    """Si A causa B, A precede a B en tiempo de historia."""
    _eventos(conn, posiciones={"ev-1": 50, "ev-2": 20})
    _causa(conn, ("ev-1", "ev-2"))

    assert GrafoCausal(conn).precedencias_violadas() == (("ev-1", "ev-2"),)


@pytest.mark.invariants
def test_no_reporta_precedencias_correctas(conn: sqlite3.Connection) -> None:
    _eventos(conn, posiciones={"ev-1": 10, "ev-2": 20})
    _causa(conn, ("ev-1", "ev-2"))

    assert GrafoCausal(conn).precedencias_violadas() == ()


# --- RF-STO-07: catalogo de predicados ----------------------------------------------


@pytest.mark.invariants
def test_el_catalogo_declara_la_exclusividad(conn: sqlite3.Connection) -> None:
    catalogo = CatalogoDePredicados(conn)

    assert catalogo.es_funcional("ubicacion") is True
    assert catalogo.es_funcional("posee") is False
    assert len(catalogo.todos()) == 9


@pytest.mark.invariants
def test_un_predicado_no_catalogado_da_error_de_dominio(conn: sqlite3.Connection) -> None:
    """El mensaje dice que hay que catalogarlo, no que fallo una clave foranea."""
    with pytest.raises(ErrorDeDominio) as error:
        CatalogoDePredicados(conn).exclusividad_de("predicado_inventado")

    assert error.value.clase == "Predicado"
    assert "RegistroDeDecision" in str(error.value)


# --- RF-STO-05: canon reconstruido desde eventos de cambio ---------------------------


@pytest.mark.invariants
def test_reconstruye_la_revision_n_sin_copiar_el_canon(conn: sqlite3.Connection) -> None:
    """«Que era verdad en el capitulo 12» se responde plegando cambios, no leyendo copias."""
    canon = CanonVersionado(conn)
    _eventos(conn, posiciones={"ev-1": 10, "ev-2": 20})

    hecho_uno = Hecho(
        id="h-1", sujeto_id="per-1", predicado="ubicacion", objeto="puerto", valido_desde="ev-1"
    )
    hecho_dos = Hecho(
        id="h-2", sujeto_id="per-1", predicado="ubicacion", objeto="faro", valido_desde="ev-2"
    )

    rev1 = canon.abrir_revision("primera canonizacion")
    canon.registrar_insercion(rev1, hecho_uno)

    rev2 = canon.abrir_revision("el personaje se muda")
    canon.registrar_cierre(rev2, "h-1", "ev-2")
    canon.registrar_insercion(rev2, hecho_dos)

    assert canon.revision_actual() == 2
    assert canon.hechos_vigentes_en(0) == frozenset()
    assert canon.hechos_vigentes_en(1) == {"h-1"}
    assert canon.hechos_vigentes_en(2) == {"h-2"}


@pytest.mark.invariants
def test_la_revision_solo_avanza(conn: sqlite3.Connection) -> None:
    """El canon se versiona; lo que deja de estar vigente conserva su intervalo."""
    canon = CanonVersionado(conn)
    primera = canon.abrir_revision()
    segunda = canon.abrir_revision()

    assert (primera, segunda) == (1, 2)
    assert canon.revision_actual() == 2
