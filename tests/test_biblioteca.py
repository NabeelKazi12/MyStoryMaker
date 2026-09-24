"""La biblioteca: todas las novelas, con su estado, para poder volver a abrirlas.

SPEC-008, PLAN-008. La ruta es de solo lectura y no calcula estados propios: reutiliza el
progreso de SPEC-004 y la aprobacion de SPEC-007, para que la biblioteca y la lectura no
puedan decir cosas distintas de la misma novela.

Cubre RF-BIB-01 a RF-BIB-04.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import main
from backend.orchestrator.aprobacion import aprobar
from backend.orchestrator.biblioteca import biblioteca
from backend.store import database
from tests.test_escritura import ENTREVISTA, _escribir, _novela

# --- A-1: la consulta -------------------------------------------------------------------


@pytest.mark.invariants
def test_la_biblioteca_trae_cada_novela_con_su_estado(conn: sqlite3.Connection) -> None:
    sin_empezar = _novela(conn, nombre="Ana")
    escrita = _novela(conn)
    _escribir(conn, escrita)
    aprobar(conn, escrita)

    novelas = {n.volumen_id: n for n in biblioteca(conn)}

    assert set(novelas) == {sin_empezar, escrita}
    vacia = novelas[sin_empezar]
    assert vacia.estado == "sin_empezar"
    assert "todavia no se ha encargado" in vacia.detalle
    assert vacia.palabras == 0
    assert vacia.ultima_version_en is None
    assert vacia.aprobacion is None
    assert vacia.destinatario == "Ana"

    llena = novelas[escrita]
    assert llena.estado == "escrita"
    assert llena.capitulos == len(ENTREVISTA["recuerdos"])  # type: ignore[arg-type]
    assert llena.palabras > 0
    assert llena.ultima_version_en is not None
    assert llena.aprobacion is not None
    assert llena.aprobacion.version_numero == 1
    assert llena.titulo


@pytest.mark.invariants
def test_la_mas_reciente_va_primero(conn: sqlite3.Connection) -> None:
    primera = _novela(conn, nombre="Ana")
    segunda = _novela(conn, nombre="Luis")
    tercera = _novela(conn, nombre="Eva")

    orden = [n.volumen_id for n in biblioteca(conn)]

    assert orden == [tercera, segunda, primera]


# --- A-2: la ruta -----------------------------------------------------------------------


@pytest.fixture
def ruta(base_plantilla: Path, tmp_path: Path) -> Path:
    copia = tmp_path / "canon.db"
    shutil.copy(base_plantilla, copia)
    return copia


@pytest.fixture
def cliente(ruta: Path) -> Iterator[TestClient]:
    def conexion_de_prueba() -> Iterator[object]:
        with database.conexion(ruta) as conn:
            yield conn

    main.app.dependency_overrides[main.obtener_conexion] = conexion_de_prueba
    try:
        yield TestClient(main.app)
    finally:
        main.app.dependency_overrides.clear()


@pytest.mark.invariants
def test_sin_novelas_la_biblioteca_esta_vacia(cliente: TestClient) -> None:
    """RF-BIB-03: vacia es `200` con lista vacia, no `404`."""
    respuesta = cliente.get("/novelas")

    assert respuesta.status_code == 200
    assert respuesta.json() == []


@pytest.mark.invariants
def test_la_ruta_sirve_lo_mismo_que_la_lectura(cliente: TestClient) -> None:
    """RF-BIB-01: titulo, destinatario y estado coinciden con las rutas de la novela."""
    volumen_id = cliente.post(
        "/entrevista", json={"respuestas": ENTREVISTA, "texto_libre": ""}
    ).json()["volumen_id"]

    novelas = cliente.get("/novelas").json()

    assert [n["volumen_id"] for n in novelas] == [volumen_id]
    novela = novelas[0]
    lectura = cliente.get(f"/novelas/{volumen_id}/lectura").json()
    progreso = cliente.get(f"/novelas/{volumen_id}/escritura").json()
    assert novela["titulo"] == lectura["titulo"]
    assert novela["destinatario"] == lectura["destinatario"]
    assert novela["aprobacion"] == lectura["aprobacion"]
    assert novela["estado"] == progreso["estado"]
    assert novela["detalle"] == progreso["detalle"]
    assert set(novela) == {
        "volumen_id",
        "titulo",
        "destinatario",
        "estado",
        "detalle",
        "capitulos",
        "palabras",
        "ultima_version_en",
        "aprobacion",
    }


@pytest.mark.invariants
def test_pedir_la_biblioteca_no_escribe_nada(cliente: TestClient, ruta: Path) -> None:
    """RF-BIB-04."""
    cliente.post("/entrevista", json={"respuestas": ENTREVISTA, "texto_libre": ""})

    def cuentas() -> tuple[int, int, int]:
        with database.conexion(ruta) as conn:
            return (
                conn.execute("SELECT COUNT(*) FROM tarea").fetchone()[0],
                conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0],
                conn.execute("SELECT COUNT(*) FROM puerta").fetchone()[0],
            )

    antes = cuentas()
    # Que responda de verdad: un 404 de ruta desconocida tampoco escribiria nada.
    assert cliente.get("/novelas").status_code == 200
    assert cliente.get("/novelas").status_code == 200

    assert cuentas() == antes


@pytest.mark.invariants
def test_la_ruta_publica_list_novelas() -> None:
    esquema = main.app.openapi()
    operaciones = {
        detalle["operationId"]
        for ruta in esquema["paths"].values()
        for detalle in ruta.values()
        if "operationId" in detalle
    }
    assert "listNovelas" in operaciones
