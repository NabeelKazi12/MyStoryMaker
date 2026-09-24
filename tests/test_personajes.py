"""Los personajes del encargo: se declaran antes de escribir y la apertura los cobra.

SPEC-011, PLAN-011. Declarar es encargar, no canonizar: el declarado vive en la capa de
especificacion y entra al canon por la apertura, que rechaza el plan entero si se deja
alguno fuera o le cambia el papel, igual que con los recuerdos obligatorios.

Cubre RF-PER-01 a RF-PER-12.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.agents.planner.planner import SalidaInvalidaDelPlanner, parsear_apertura
from backend.api import main
from backend.domain.errors import ErrorDeDominio
from backend.domain.spec.encargo import PersonajeDeclarado
from backend.domain.vocabularies import Relevancia
from backend.orchestrator.apertura import instruccion_de_apertura, leer_encargo
from backend.store import database
from tests.test_escritura import APERTURA_BUENA, ENTREVISTA, _escribir, _novela, _vaciar_la_cola

HERMANO = {
    "nombre": "Luis",
    "papel": "secundario",
    "relacion": "su hermano pequeño",
    "descripcion": "Le sigue a todas partes y nunca calla.",
}


def _declarados(conn: sqlite3.Connection, volumen_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT pd.nombre, pd.papel, pd.relacion, pd.descripcion, pd.es_destinatario
        FROM personaje_declarado pd
        JOIN volumen v ON v.brief_id = pd.brief_id
        WHERE v.id = ?
        ORDER BY pd.orden
        """,
        (volumen_id,),
    ).fetchall()


# --- A-1: la clase y la tabla -----------------------------------------------------------


@pytest.mark.invariants
def test_un_declarado_sin_nombre_no_valida() -> None:
    with pytest.raises(ErrorDeDominio):
        PersonajeDeclarado(id="x", nombre="   ", papel=Relevancia.SECUNDARIO)
    with pytest.raises(ErrorDeDominio):
        PersonajeDeclarado(id="x", nombre="a" * 81, papel=Relevancia.SECUNDARIO)
    with pytest.raises(ErrorDeDominio):
        PersonajeDeclarado(
            id="x", nombre="Luis", papel=Relevancia.SECUNDARIO, descripcion="d" * 501
        )


@pytest.mark.invariants
def test_migracion_0008_crea_personaje_declarado(conn: sqlite3.Connection) -> None:
    columnas = {
        f["name"] for f in conn.execute("PRAGMA table_info(personaje_declarado)").fetchall()
    }
    assert {
        "id",
        "brief_id",
        "orden",
        "nombre",
        "papel",
        "relacion",
        "descripcion",
        "es_destinatario",
    } <= columnas
    registradas = {f["id"] for f in conn.execute("SELECT id FROM registro_decision").fetchall()}
    assert "rd-d25" in registradas


# --- A-2: la entrevista -----------------------------------------------------------------


@pytest.mark.invariants
def test_sin_personajes_se_declara_la_destinataria(conn: sqlite3.Connection) -> None:
    """RF-PER-02."""
    volumen_id = _novela(conn)

    (unico,) = _declarados(conn, volumen_id)

    assert unico["nombre"] == ENTREVISTA["nombre"]
    assert unico["papel"] == "protagonico"
    assert unico["es_destinatario"] == 1
    assert unico["relacion"] == "a quien va dedicada"


@pytest.mark.invariants
def test_la_destinataria_siempre_es_protagonista(conn: sqlite3.Connection) -> None:
    """Si llega con otro papel se corrige; su descripcion se conserva."""
    volumen_id = _novela(
        conn,
        personajes=[
            {
                "nombre": "otro nombre",
                "papel": "secundario",
                "descripcion": "Terca como ella sola.",
                "es_destinatario": True,
            },
            HERMANO,
        ],
    )

    destinataria, hermano = _declarados(conn, volumen_id)

    assert destinataria["nombre"] == ENTREVISTA["nombre"]
    assert destinataria["papel"] == "protagonico"
    assert destinataria["descripcion"] == "Terca como ella sola."
    assert hermano["nombre"] == "Luis"
    assert hermano["papel"] == "secundario"
    assert hermano["relacion"] == "su hermano pequeño"


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


def _entrevista(cliente: TestClient, personajes: object) -> object:
    return cliente.post(
        "/entrevista",
        json={"respuestas": {**ENTREVISTA, "personajes": personajes}, "texto_libre": ""},
    )


def _briefs(ruta: Path) -> int:
    with database.conexion(ruta) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM brief").fetchone()[0])


@pytest.mark.invariants
def test_un_nombre_repetido_da_422_sin_crear_nada(cliente: TestClient, ruta: Path) -> None:
    """RF-PER-03, RF-PER-04: «Luis» y «luís» son el mismo nombre."""
    respuesta = _entrevista(cliente, [HERMANO, {**HERMANO, "nombre": "luís"}])

    assert respuesta.status_code == 422
    detalle = respuesta.json()["detail"]
    choque = next(c for c in detalle["contradicciones"] if "personajes" in c["campos"])
    assert "luís" in choque["detalle"].lower()
    assert _briefs(ruta) == 0


@pytest.mark.invariants
def test_un_personaje_con_el_nombre_de_la_destinataria_da_422(
    cliente: TestClient, ruta: Path
) -> None:
    respuesta = _entrevista(cliente, [{**HERMANO, "nombre": ENTREVISTA["nombre"]}])

    assert respuesta.status_code == 422
    assert _briefs(ruta) == 0


@pytest.mark.invariants
@pytest.mark.parametrize(
    "malo",
    [
        {**HERMANO, "nombre": ""},
        {**HERMANO, "nombre": "x" * 81},
        {**HERMANO, "papel": "villano"},
        {**HERMANO, "descripcion": "d" * 501},
        "no es un personaje",
    ],
    ids=["vacio", "largo", "papel", "descripcion", "forma"],
)
def test_un_personaje_mal_formado_da_422(cliente: TestClient, ruta: Path, malo: object) -> None:
    respuesta = _entrevista(cliente, [malo])

    assert respuesta.status_code == 422
    assert any(
        "personajes" in c["campos"] for c in respuesta.json()["detail"]["contradicciones"]
    )
    assert _briefs(ruta) == 0


@pytest.mark.invariants
def test_trece_personajes_dan_422(cliente: TestClient, ruta: Path) -> None:
    """Doce en total, la destinataria incluida."""
    doce = [{**HERMANO, "nombre": f"Persona {n}"} for n in range(1, 12)]
    assert _entrevista(cliente, doce).status_code == 201

    trece = [{**HERMANO, "nombre": f"Persona {n}"} for n in range(1, 13)]
    assert _entrevista(cliente, trece).status_code == 422


# --- B-1: la instruccion ----------------------------------------------------------------


@pytest.mark.invariants
def test_la_instruccion_lleva_cada_declarado(conn: sqlite3.Connection) -> None:
    """RF-PER-05. La barra del contrato no puede partir la fila."""
    volumen_id = _novela(conn, personajes=[{**HERMANO, "descripcion": "sigue | a todos"}])

    instruccion = instruccion_de_apertura(leer_encargo(conn, volumen_id))

    assert (
        f"personaje declarado | {ENTREVISTA['nombre']} | protagonico | a quien va dedicada |"
        in instruccion
    )
    assert "personaje declarado | Luis | secundario | su hermano pequeño | sigue / a todos" in (
        instruccion
    )


# --- B-2: la cobertura en la apertura ---------------------------------------------------


@pytest.mark.invariants
def test_un_plan_sin_un_declarado_se_rechaza_nombrandolo() -> None:
    """RF-PER-06."""
    with pytest.raises(SalidaInvalidaDelPlanner) as error:
        parsear_apertura(
            APERTURA_BUENA,
            personajes_declarados=(
                ("Marta", Relevancia.PROTAGONICO),
                ("Luis", Relevancia.SECUNDARIO),
            ),
        )

    assert "Luis" in str(error.value)
    assert "Marta" not in str(error.value)


@pytest.mark.invariants
def test_un_declarado_con_otro_papel_se_rechaza() -> None:
    with pytest.raises(SalidaInvalidaDelPlanner) as error:
        parsear_apertura(
            APERTURA_BUENA, personajes_declarados=(("Marta", Relevancia.SECUNDARIO),)
        )

    assert "Marta" in str(error.value)
    assert "secundario" in str(error.value)


@pytest.mark.invariants
def test_un_declarado_que_no_sale_en_ninguna_escena_se_rechaza() -> None:
    """RF-PER-06: «aparecer» es salir en la historia, no solo estar en la lista."""
    listado_y_nada_mas = APERTURA_BUENA.replace(
        "## lugares", "- p2 | Luis | secundario | - | -\n\n## lugares"
    )

    with pytest.raises(SalidaInvalidaDelPlanner) as error:
        parsear_apertura(
            listado_y_nada_mas,
            personajes_declarados=(
                ("Marta", Relevancia.PROTAGONICO),
                ("Luis", Relevancia.SECUNDARIO),
            ),
        )

    assert "Luis" in str(error.value)
    assert "ninguna escena" in str(error.value)


@pytest.mark.invariants
def test_el_planner_puede_anadir_personajes() -> None:
    """RF-PER-07, y el nombre se compara sin mayusculas ni acentos."""
    con_otro = APERTURA_BUENA.replace(
        "## lugares", "- p2 | Luis | secundario | - | -\n\n## lugares"
    )

    apertura = parsear_apertura(
        con_otro, personajes_declarados=(("MÁRTA", Relevancia.PROTAGONICO),)
    )

    assert {p.nombre_canonico for p in apertura.personajes} == {"Marta", "Luis"}


# --- B-3: la demostracion ---------------------------------------------------------------


@pytest.mark.invariants
def test_una_muestra_lleva_los_personajes_declarados_al_canon(conn: sqlite3.Connection) -> None:
    """RF-PER-12: el modo demostracion tambien cumple RF-PER-06."""
    volumen_id = _novela(conn, personajes=[HERMANO])

    _escribir(conn, volumen_id)

    capitulos = conn.execute(
        "SELECT COUNT(*) FROM capitulo WHERE volumen_id = ?", (volumen_id,)
    ).fetchone()[0]
    assert capitulos > 0
    hermano = conn.execute(
        "SELECT relevancia FROM personaje WHERE nombre_canonico = 'Luis'"
    ).fetchone()
    assert hermano is not None and hermano["relevancia"] == "secundario"
    # Y sale en la novela: la ficha de la lectura lo encuentra por sus escenas.
    ficha = {
        p["nombre_canonico"] for p in main.lectura_de_novela(volumen_id, conn)["personajes"]
    }
    assert "Luis" in ficha


# --- C-1: las rutas ---------------------------------------------------------------------


def _novela_por_la_ruta(cliente: TestClient, personajes: object = ()) -> str:
    respuesta = _entrevista(cliente, list(personajes))  # type: ignore[call-overload]
    assert respuesta.status_code == 201, respuesta.text  # type: ignore[attr-defined]
    return str(respuesta.json()["volumen_id"])  # type: ignore[attr-defined]


@pytest.mark.invariants
def test_leer_y_reemplazar_los_personajes(cliente: TestClient) -> None:
    """RF-PER-08."""
    volumen_id = _novela_por_la_ruta(cliente, [HERMANO])

    leidos = cliente.get(f"/novelas/{volumen_id}/personajes").json()["personajes"]
    assert [p["nombre"] for p in leidos] == [ENTREVISTA["nombre"], "Luis"]
    assert leidos[0]["es_destinatario"] is True

    nuevos = [
        {**leidos[0], "descripcion": "Ahora con descripción."},
        {"nombre": "Abuela Rosa", "papel": "ambiental", "relacion": "", "descripcion": ""},
    ]
    respuesta = cliente.put(f"/novelas/{volumen_id}/personajes", json={"personajes": nuevos})

    assert respuesta.status_code == 200, respuesta.text
    guardados = respuesta.json()["personajes"]
    assert [p["nombre"] for p in guardados] == [ENTREVISTA["nombre"], "Abuela Rosa"]
    assert guardados[0]["descripcion"] == "Ahora con descripción."
    assert cliente.get(f"/novelas/{volumen_id}/personajes").json()["personajes"] == guardados


@pytest.mark.invariants
def test_reemplazar_con_un_nombre_repetido_da_422(cliente: TestClient) -> None:
    volumen_id = _novela_por_la_ruta(cliente, [HERMANO])

    respuesta = cliente.put(
        f"/novelas/{volumen_id}/personajes",
        json={"personajes": [HERMANO, {**HERMANO, "nombre": "LUIS"}]},
    )

    assert respuesta.status_code == 422
    assert [
        p["nombre"]
        for p in cliente.get(f"/novelas/{volumen_id}/personajes").json()["personajes"]
    ] == [ENTREVISTA["nombre"], "Luis"]


@pytest.mark.invariants
def test_con_la_escritura_empezada_no_se_editan(cliente: TestClient) -> None:
    """RF-PER-09: encolada, la escritura ya no esta `sin_empezar`."""
    volumen_id = _novela_por_la_ruta(cliente, [HERMANO])
    cliente.post(f"/novelas/{volumen_id}/escritura", json={"modo": "demostracion"})

    respuesta = cliente.put(f"/novelas/{volumen_id}/personajes", json={"personajes": []})

    assert respuesta.status_code == 409
    assert "pide un cambio" in respuesta.json()["detail"]


@pytest.mark.invariants
def test_una_aprobada_no_se_edita(cliente: TestClient, ruta: Path) -> None:
    volumen_id = _novela_por_la_ruta(cliente)
    cliente.post(f"/novelas/{volumen_id}/escritura", json={"modo": "demostracion"})
    _vaciar_la_cola(ruta)
    assert cliente.post(f"/novelas/{volumen_id}/aprobacion").status_code == 201

    respuesta = cliente.put(f"/novelas/{volumen_id}/personajes", json={"personajes": []})

    assert respuesta.status_code == 409


@pytest.mark.invariants
def test_editar_queda_en_audit_log(cliente: TestClient, ruta: Path) -> None:
    """RF-PER-10."""
    volumen_id = _novela_por_la_ruta(cliente, [HERMANO])

    cliente.put(f"/novelas/{volumen_id}/personajes", json={"personajes": []})

    with database.conexion(ruta) as conn:
        fila = conn.execute(
            "SELECT motivo FROM audit_log WHERE decision = 'editar_personajes'"
        ).fetchone()
    assert fila is not None
    assert "Luis" in fila["motivo"]


@pytest.mark.invariants
def test_las_rutas_de_personajes_publican_operation_id() -> None:
    esquema = main.app.openapi()
    operaciones = {
        detalle["operationId"]
        for ruta in esquema["paths"].values()
        for detalle in ruta.values()
        if "operationId" in detalle
    }
    assert {"readPersonajes", "updatePersonajes"} <= operaciones
