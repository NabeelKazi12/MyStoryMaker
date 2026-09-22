"""Frontera de la API: altas validadas, `202` sin bloqueo, SSE y lecturas.

Cubre RF-API-01 a RF-API-07.
"""

from __future__ import annotations

import inspect
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import main
from backend.store import database

ESCENA_VALIDA = {
    "id": "esc-1",
    "capitulo_id": "cap-1",
    "orden": 1,
    "pov_id": "per-1",
    "lugar_id": "lug-1",
    "momento_en_historia": 10,
    "objetivo": "recuperar la carta",
    "conflicto": "el guardia no se mueve",
    "resultado": "la consigue pero la ven",
    "valor_entrada": "seguro",
    "valor_salida": "expuesto",
    "funcion_en_trama": "complicacion",
    "tipo": "accion",
    "renderiza": ["ev-1"],
    "hechos_requeridos": ["h-1"],
}


@pytest.fixture
def cliente(base_plantilla: Path, tmp_path: Path) -> Iterator[TestClient]:
    """Cliente sobre una copia limpia de la base migrada."""
    copia = tmp_path / "canon.db"
    shutil.copy(base_plantilla, copia)

    def conexion_de_prueba() -> Iterator[object]:
        with database.conexion(copia) as conn:
            yield conn

    main.app.dependency_overrides[main.obtener_conexion] = conexion_de_prueba
    with database.conexion(copia) as conn:
        from tests.conftest import material_minimo

        material_minimo(conn, con_escena=False)
    try:
        yield TestClient(main.app)
    finally:
        main.app.dependency_overrides.clear()


# --- RF-API-01: altas ----------------------------------------------------------------


@pytest.mark.invariants
def test_alta_de_brief(cliente: TestClient) -> None:
    respuesta = cliente.post(
        "/brief",
        json={
            "id": "br-1",
            "genero": "misterio",
            "premisa": "una carta que no deberia existir",
            "promesa_al_lector": "el misterio se resuelve",
            "extension_objetivo": 120_000,
        },
    )
    assert respuesta.status_code == 201


@pytest.mark.invariants
def test_un_brief_sin_promesa_al_lector_se_rechaza(cliente: TestClient) -> None:
    """La validacion ocurre en el backend, siempre."""
    respuesta = cliente.post(
        "/brief",
        json={
            "id": "br-2",
            "genero": "misterio",
            "premisa": "algo",
            "promesa_al_lector": "   ",
            "extension_objetivo": 120_000,
        },
    )
    assert respuesta.status_code == 422
    assert "promesa_al_lector" in respuesta.json()["detail"]


# --- RF-API-02: el esqueleto exige sus campos obligatorios ---------------------------


@pytest.mark.invariants
def test_alta_de_escena_con_todos_los_campos(cliente: TestClient) -> None:
    assert cliente.post("/escenas", json=ESCENA_VALIDA).status_code == 201


@pytest.mark.invariants
@pytest.mark.parametrize("campo", ["hechos_requeridos", "renderiza", "valor_salida"])
def test_una_escena_sin_un_campo_obligatorio_da_422(cliente: TestClient, campo: str) -> None:
    incompleta = {k: v for k, v in ESCENA_VALIDA.items() if k != campo}
    assert cliente.post("/escenas", json=incompleta).status_code == 422


@pytest.mark.invariants
def test_una_escena_sin_cambio_de_valor_da_422(cliente: TestClient) -> None:
    """El invariante del dominio llega hasta la frontera."""
    igual = {**ESCENA_VALIDA, "valor_salida": ESCENA_VALIDA["valor_entrada"]}
    respuesta = cliente.post("/escenas", json=igual)
    assert respuesta.status_code == 422
    assert "valor_entrada" in respuesta.json()["detail"]


# --- RF-API-03: generacion encolada, nunca bloqueante -------------------------------


@pytest.mark.invariants
def test_pedir_redaccion_devuelve_202_con_id_de_tarea(cliente: TestClient) -> None:
    cliente.post("/escenas", json=ESCENA_VALIDA)
    respuesta = cliente.post("/escenas/esc-1/redactar")

    assert respuesta.status_code == 202
    assert respuesta.json()["tarea_id"] == "esc-1:redaccion"
    assert respuesta.json()["estado"] == "pendiente"


@pytest.mark.invariants
def test_el_estado_de_una_tarea_se_puede_consultar(cliente: TestClient) -> None:
    cliente.post("/escenas", json=ESCENA_VALIDA)
    cliente.post("/escenas/esc-1/redactar")

    respuesta = cliente.get("/tareas/esc-1:redaccion")
    assert respuesta.status_code == 200
    assert respuesta.json()["intentos_narrativos"] == 0


@pytest.mark.invariants
def test_una_tarea_inexistente_da_404(cliente: TestClient) -> None:
    assert cliente.get("/tareas/no-existe").status_code == 404


# --- RF-API-04: SSE ------------------------------------------------------------------


@pytest.mark.invariants
def test_el_flujo_de_eventos_es_event_stream(cliente: TestClient) -> None:
    respuesta = cliente.get("/tareas/esc-1:redaccion/eventos")
    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/event-stream")


# --- RF-API-05: lecturas -------------------------------------------------------------


@pytest.mark.invariants
def test_las_puertas_exponen_su_evidencia_ausente(cliente: TestClient) -> None:
    """Una puerta no dice solo si paso: dice tambien lo que no pudo comprobar."""
    respuesta = cliente.get("/puertas")
    assert respuesta.status_code == 200


@pytest.mark.invariants
def test_el_catalogo_de_predicados_es_de_solo_lectura(cliente: TestClient) -> None:
    """Se amplia por migracion con RegistroDeDecision, no por un endpoint de alta (R-7)."""
    respuesta = cliente.get("/predicados")
    assert respuesta.status_code == 200
    assert len(respuesta.json()) == 9
    assert cliente.post("/predicados", json={"nombre": "x"}).status_code in (404, 405)


# --- RF-API-06 y RF-API-07: la frontera ----------------------------------------------


@pytest.mark.invariants
def test_ninguna_clase_del_dominio_aparece_en_una_firma_de_ruta() -> None:
    """Los modelos Pydantic son la frontera de serializacion, no las clases del dominio."""
    prohibidas = {"Escena", "Brief", "Hecho", "Tarea", "Borrador", "Defecto", "Personaje"}
    for ruta in main.app.routes:
        funcion = getattr(ruta, "endpoint", None)
        if funcion is None:
            continue
        for parametro in inspect.signature(funcion).parameters.values():
            nombre = getattr(parametro.annotation, "__name__", "")
            assert nombre not in prohibidas, f"{funcion.__name__} expone {nombre}"


@pytest.mark.invariants
def test_la_api_no_alcanza_el_cliente_de_modelo() -> None:
    """`api/` encola y lee estado; el trabajo ocurre en `worker/`."""
    fuente = Path(main.__file__).read_text(encoding="utf-8")
    assert "backend.worker" not in fuente
    assert "invocar" not in fuente
