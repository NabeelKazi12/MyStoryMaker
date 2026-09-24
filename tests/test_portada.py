"""El titulo y la dedicatoria se editan despues de la entrevista.

SPEC-006, PLAN-006 A-1. La ruta cambia como se presenta la novela y nada de lo que cuenta:
ni prosa, ni canon, ni tareas, ni versiones.

Cubre RF-POR-01 a RF-POR-07.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import main
from backend.store import database
from tests.test_escritura import ENTREVISTA, _vaciar_la_cola


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


def _novela(cliente: TestClient, **cambios: object) -> str:
    respuestas = {**ENTREVISTA, **cambios}
    respuesta = cliente.post("/entrevista", json={"respuestas": respuestas, "texto_libre": ""})
    assert respuesta.status_code == 201
    return str(respuesta.json()["volumen_id"])


@pytest.mark.invariants
def test_cambia_titulo_y_dedicatoria_y_se_ven_en_la_lectura(cliente: TestClient) -> None:
    """RF-POR-01, RF-POR-06."""
    volumen_id = _novela(cliente)

    respuesta = cliente.patch(
        f"/novelas/{volumen_id}/portada",
        json={"titulo": "  El agua fría  ", "dedicatoria": " Para quien vuelve. "},
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {
        "volumen_id": volumen_id,
        "titulo": "El agua fría",
        "dedicatoria": "Para quien vuelve.",
    }
    lectura = cliente.get(f"/novelas/{volumen_id}/lectura").json()
    assert lectura["titulo"] == "El agua fría"
    assert lectura["dedicatoria"] == "Para quien vuelve."
    assert cliente.get(f"/novelas/{volumen_id}/texto").json()["titulo"] == "El agua fría"


@pytest.mark.invariants
def test_basta_con_uno_de_los_dos_y_el_otro_no_cambia(cliente: TestClient) -> None:
    volumen_id = _novela(cliente)

    cliente.patch(f"/novelas/{volumen_id}/portada", json={"titulo": "Solo el título"})

    lectura = cliente.get(f"/novelas/{volumen_id}/lectura").json()
    assert lectura["titulo"] == "Solo el título"
    assert lectura["dedicatoria"] == ENTREVISTA["dedicatoria"]


@pytest.mark.invariants
def test_sin_ningun_campo_es_422(cliente: TestClient) -> None:
    volumen_id = _novela(cliente)
    respuesta = cliente.patch(f"/novelas/{volumen_id}/portada", json={})
    assert respuesta.status_code == 422


@pytest.mark.invariants
@pytest.mark.parametrize(
    ("titulo", "limite"),
    [("   ", "vacio"), ("x" * 121, "120")],
)
def test_un_titulo_fuera_de_limites_es_422_y_dice_cual(
    cliente: TestClient, titulo: str, limite: str
) -> None:
    """RF-POR-02."""
    volumen_id = _novela(cliente)

    respuesta = cliente.patch(f"/novelas/{volumen_id}/portada", json={"titulo": titulo})

    assert respuesta.status_code == 422
    assert limite in respuesta.json()["detail"]
    assert cliente.get(f"/novelas/{volumen_id}/lectura").json()["titulo"] != titulo


@pytest.mark.invariants
def test_una_dedicatoria_vacia_quita_la_dedicatoria(cliente: TestClient) -> None:
    """RF-POR-03."""
    volumen_id = _novela(cliente)

    respuesta = cliente.patch(f"/novelas/{volumen_id}/portada", json={"dedicatoria": "  "})

    assert respuesta.status_code == 200
    assert cliente.get(f"/novelas/{volumen_id}/lectura").json()["dedicatoria"] == ""


@pytest.mark.invariants
def test_una_dedicatoria_de_mas_de_500_es_422(cliente: TestClient) -> None:
    volumen_id = _novela(cliente)
    respuesta = cliente.patch(f"/novelas/{volumen_id}/portada", json={"dedicatoria": "x" * 501})
    assert respuesta.status_code == 422
    assert "500" in respuesta.json()["detail"]


@pytest.mark.invariants
@pytest.mark.parametrize("campo", ["titulo", "dedicatoria"])
def test_un_termino_vetado_es_422_y_no_guarda_nada(cliente: TestClient, campo: str) -> None:
    """RF-POR-04. El guardarrail vale para todo texto del regalo, no solo la prosa."""
    volumen_id = _novela(cliente, palabras_vetadas=["espejo"])
    antes = cliente.get(f"/novelas/{volumen_id}/lectura").json()

    respuesta = cliente.patch(
        f"/novelas/{volumen_id}/portada",
        json={"titulo": "Otro título", campo: "El espejo roto"},
    )

    assert respuesta.status_code == 422
    assert "espejo" in respuesta.json()["detail"]
    despues = cliente.get(f"/novelas/{volumen_id}/lectura").json()
    assert (despues["titulo"], despues["dedicatoria"]) == (
        antes["titulo"],
        antes["dedicatoria"],
    )


@pytest.mark.invariants
def test_una_novela_que_no_existe_es_404(cliente: TestClient) -> None:
    """RF-POR-05."""
    respuesta = cliente.patch("/novelas/vol-no-existe/portada", json={"titulo": "X"})
    assert respuesta.status_code == 404


@pytest.mark.invariants
def test_no_toca_prosa_tareas_ni_versiones(cliente: TestClient, ruta: Path) -> None:
    """RF-POR-06. Cambiar como se presenta no cambia lo que se cuenta."""
    volumen_id = _novela(cliente)
    cliente.post(f"/novelas/{volumen_id}/escritura", json={"modo": "demostracion"})
    _vaciar_la_cola(ruta)

    def estado() -> tuple[object, ...]:
        with database.conexion(ruta) as conn:
            return tuple(
                tuple(tuple(fila) for fila in conn.execute(consulta).fetchall())
                for consulta in (
                    "SELECT id, texto, estado FROM borrador ORDER BY id",
                    "SELECT id, estado FROM tarea ORDER BY id",
                    "SELECT id FROM version_novela ORDER BY id",
                    "SELECT id FROM hecho ORDER BY id",
                )
            )

    antes = estado()
    cliente.patch(f"/novelas/{volumen_id}/portada", json={"titulo": "Nuevo", "dedicatoria": ""})

    assert estado() == antes
    pdf = cliente.get(f"/novelas/{volumen_id}/pdf")
    assert pdf.status_code == 200
    assert "Nuevo" in pdf.headers["content-disposition"]


@pytest.mark.invariants
def test_cada_cambio_queda_en_el_audit_log(cliente: TestClient, ruta: Path) -> None:
    """RF-POR-07. Con el valor anterior y el nuevo."""
    volumen_id = _novela(cliente)
    anterior = cliente.get(f"/novelas/{volumen_id}/lectura").json()["titulo"]

    cliente.patch(f"/novelas/{volumen_id}/portada", json={"titulo": "El agua fría"})

    with database.conexion(ruta) as conn:
        filas = conn.execute(
            "SELECT motivo FROM audit_log WHERE decision = 'editar_portada'"
        ).fetchall()
    assert len(filas) == 1
    assert anterior in filas[0]["motivo"]
    assert "El agua fría" in filas[0]["motivo"]


@pytest.mark.invariants
def test_la_ruta_publica_su_operation_id() -> None:
    operaciones = {
        detalle.get("operationId")
        for ruta in main.app.openapi()["paths"].values()
        for detalle in ruta.values()
    }
    assert "updatePortada" in operaciones
