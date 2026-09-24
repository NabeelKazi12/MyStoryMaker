"""Eliminar una novela: se retira, no se borra.

SPEC-009, PLAN-009. La novela retirada desaparece de la biblioteca y de todas las rutas,
pero sus filas se quedan: borrarlas romperia `VersionAnteriorSeConserva`, el trigger de
aprobaciones de `0005` y la inmutabilidad de `audit_log` (SPEC-009 P-2).

Cubre RF-ELI-01 a RF-ELI-08.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import main
from backend.domain.vocabularies import ModoDeEscritura
from backend.orchestrator.aprobacion import aprobar
from backend.orchestrator.biblioteca import biblioteca
from backend.orchestrator.eliminacion import EliminacionRechazada, eliminar
from backend.orchestrator.escritura import encolar_escritura
from backend.store import database
from tests.test_escritura import ENTREVISTA, _escribir, _novela, _vaciar_la_cola

# Las tablas cuyas filas una retirada no puede tocar (RF-ELI-07).
TABLAS_CONSERVADAS = (
    "capitulo",
    "escena",
    "borrador",
    "version_novela",
    "version_capitulo",
    "aprobacion_de_volumen",
    "tarea",
    "hecho",
    "personaje",
    "lugar",
    "registro_decision",
)


def _cuentas(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLAS_CONSERVADAS
    }


# --- A-1: esquema ----------------------------------------------------------------------


@pytest.mark.invariants
def test_migracion_0006_anade_eliminada_en(conn: sqlite3.Connection) -> None:
    columnas = {f["name"] for f in conn.execute("PRAGMA table_info(volumen)").fetchall()}
    assert "eliminada_en" in columnas
    registradas = {f["id"] for f in conn.execute("SELECT id FROM registro_decision").fetchall()}
    assert "rd-d23" in registradas


# --- B-1: la retirada -------------------------------------------------------------------


@pytest.mark.invariants
def test_eliminar_marca_la_fecha_y_no_toca_nada_mas(conn: sqlite3.Connection) -> None:
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)
    antes = _cuentas(conn)

    retirada = eliminar(conn, volumen_id)

    assert retirada.volumen_id == volumen_id
    assert retirada.titulo
    assert retirada.eliminada_en
    fila = conn.execute(
        "SELECT eliminada_en FROM volumen WHERE id = ?", (volumen_id,)
    ).fetchone()
    assert fila["eliminada_en"] == retirada.eliminada_en
    assert _cuentas(conn) == antes


@pytest.mark.invariants
def test_una_sin_empezar_tambien_se_elimina(conn: sqlite3.Connection) -> None:
    volumen_id = _novela(conn)

    assert eliminar(conn, volumen_id).volumen_id == volumen_id


@pytest.mark.invariants
def test_una_aprobada_no_se_elimina(conn: sqlite3.Connection) -> None:
    """RF-ELI-02."""
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)
    aprobar(conn, volumen_id)

    with pytest.raises(EliminacionRechazada, match="reábrela antes de eliminarla"):
        eliminar(conn, volumen_id)

    fila = conn.execute(
        "SELECT eliminada_en FROM volumen WHERE id = ?", (volumen_id,)
    ).fetchone()
    assert fila["eliminada_en"] is None


@pytest.mark.invariants
def test_una_en_curso_no_se_elimina(conn: sqlite3.Connection) -> None:
    """RF-ELI-03: encolada y sin worker, esta abriendose."""
    volumen_id = _novela(conn)
    encolar_escritura(conn, volumen_id, ModoDeEscritura.DEMOSTRACION)

    with pytest.raises(EliminacionRechazada) as rechazo:
        eliminar(conn, volumen_id)

    assert "abriendo" in str(rechazo.value)
    fila = conn.execute(
        "SELECT eliminada_en FROM volumen WHERE id = ?", (volumen_id,)
    ).fetchone()
    assert fila["eliminada_en"] is None


@pytest.mark.invariants
def test_eliminar_queda_en_audit_log(conn: sqlite3.Connection) -> None:
    """RF-ELI-08."""
    volumen_id = _novela(conn)
    titulo = conn.execute("SELECT titulo FROM volumen WHERE id = ?", (volumen_id,)).fetchone()[
        0
    ]

    eliminar(conn, volumen_id)

    fila = conn.execute(
        "SELECT motivo FROM audit_log WHERE decision = 'eliminar_novela'"
    ).fetchone()
    assert volumen_id in fila["motivo"]
    assert titulo in fila["motivo"]


# --- B-2: la biblioteca -----------------------------------------------------------------


@pytest.mark.invariants
def test_la_biblioteca_no_lista_las_eliminadas(conn: sqlite3.Connection) -> None:
    """RF-ELI-06."""
    queda = _novela(conn, nombre="Ana")
    se_va = _novela(conn, nombre="Luis")

    eliminar(conn, se_va)

    assert [n.volumen_id for n in biblioteca(conn)] == [queda]


# --- C-1: las rutas ---------------------------------------------------------------------


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


def _novela_por_la_ruta(cliente: TestClient) -> str:
    return str(
        cliente.post("/entrevista", json={"respuestas": ENTREVISTA, "texto_libre": ""}).json()[
            "volumen_id"
        ]
    )


@pytest.mark.invariants
def test_eliminar_por_la_ruta(cliente: TestClient, ruta: Path) -> None:
    """RF-ELI-01."""
    volumen_id = _novela_por_la_ruta(cliente)
    cliente.post(f"/novelas/{volumen_id}/escritura", json={"modo": "demostracion"})
    _vaciar_la_cola(ruta)

    respuesta = cliente.delete(f"/novelas/{volumen_id}")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["volumen_id"] == volumen_id
    assert cuerpo["titulo"]
    assert cuerpo["eliminada_en"]
    assert cliente.get("/novelas").json() == []


@pytest.mark.invariants
def test_eliminar_dos_veces_da_404(cliente: TestClient) -> None:
    """RF-ELI-04."""
    volumen_id = _novela_por_la_ruta(cliente)
    cliente.delete(f"/novelas/{volumen_id}")

    for ruta in (f"/novelas/{volumen_id}", "/novelas/vol-no-existe"):
        respuesta = cliente.delete(ruta)
        assert respuesta.status_code == 404
        assert "no existe el volumen" in respuesta.json()["detail"]


@pytest.mark.invariants
def test_eliminar_una_aprobada_por_la_ruta_da_409(cliente: TestClient, ruta: Path) -> None:
    volumen_id = _novela_por_la_ruta(cliente)
    cliente.post(f"/novelas/{volumen_id}/escritura", json={"modo": "demostracion"})
    _vaciar_la_cola(ruta)
    cliente.post(f"/novelas/{volumen_id}/aprobacion")

    respuesta = cliente.delete(f"/novelas/{volumen_id}")

    assert respuesta.status_code == 409
    assert "reábrela antes de eliminarla" in respuesta.json()["detail"]
    assert [n["volumen_id"] for n in cliente.get("/novelas").json()] == [volumen_id]


# Un cuerpo que valida en todas las rutas con cuerpo: los campos que una ruta no declara
# se ignoran. Sin el, una ruta podria responder 422 antes de mirar si la novela existe, y
# el test no distinguiria una comprobacion olvidada de un cuerpo mal formado.
CUERPO_VALIDO = {
    "hecho_id": "h-1",
    "descripcion": "otro",
    "modo": "demostracion",
    "titulo": "X",
}


@pytest.mark.invariants
def test_ninguna_ruta_sirve_una_novela_eliminada(cliente: TestClient) -> None:
    """RF-ELI-05: recorre **todas** las rutas con `{volumen_id}`, las de hoy y las futuras."""
    volumen_id = _novela_por_la_ruta(cliente)
    cliente.delete(f"/novelas/{volumen_id}")

    rutas = [
        (metodo, r.path)
        for r in main.app.routes
        if "{volumen_id}" in getattr(r, "path", "")
        for metodo in sorted(getattr(r, "methods", set()) - {"HEAD", "OPTIONS"})
    ]
    assert len(rutas) >= 11, rutas

    for metodo, plantilla in rutas:
        url = plantilla.replace("{volumen_id}", volumen_id)
        respuesta = cliente.request(
            metodo, url, json=CUERPO_VALIDO if metodo in ("POST", "PATCH") else None
        )
        assert respuesta.status_code == 404, f"{metodo} {plantilla}: {respuesta.status_code}"
        assert "no existe el volumen" in str(respuesta.json()["detail"]), (
            f"{metodo} {plantilla}"
        )


@pytest.mark.invariants
def test_la_ruta_publica_delete_novela() -> None:
    esquema = main.app.openapi()
    operaciones = {
        detalle["operationId"]
        for ruta in esquema["paths"].values()
        for detalle in ruta.values()
        if "operationId" in detalle
    }
    assert "deleteNovela" in operaciones
