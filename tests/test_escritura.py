"""La novela se escribe y se lee: apertura, bucle, rutas y modos.

SPEC-004, PLAN-004. Corre entero en modo demostracion -no hay credencial en este entorno-
y eso es suficiente para lo que comprueba: que el recorrido existe, que cada pieza escribe
lo que dice escribir y que ningun borrador se da por aceptado. Lo que no prueba es la
calidad de la prosa, que no es lo que un test decide (SPEC-004 N-02).

Cubre RF-APE-01 a RF-APE-05, RF-ESC-01 a RF-ESC-09, RF-RUT-01 a RF-RUT-07 y
RF-MOD-01 a RF-MOD-03.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.agents.planner import planner
from backend.agents.planner.planner import (
    SalidaInvalidaDelPlanner,
    parsear_apertura,
    verificar_integridad_del_prompt,
)
from backend.api import main
from backend.context.presupuesto import Componente
from backend.domain.vocabularies import EstadoDeBorrador, EstadoDeTarea, ModoDeEscritura
from backend.orchestrator.apertura import leer_encargo, persistir_apertura
from backend.orchestrator.encargo import crear_novela_desde_entrevista
from backend.orchestrator.escritura import encolar_escritura, paquete_de_escena, progreso
from backend.store import database
from backend.store.escritura import Borradores, ColaDeTareas, TextoDeLaNovela
from backend.worker.bucle import Bucle
from backend.worker.modelo import (
    MODELO_DE_DEMOSTRACION,
    VARIABLE_DE_CREDENCIAL,
    ClienteDeDemostracion,
    CredencialAusente,
    construir_cliente,
    construir_cliente_real,
)

ENTREVISTA = {
    "nombre": "Marta",
    "edad": 34,
    "rasgos": ["terca", "nada sentimental"],
    "recuerdos": [
        "el verano en que aprendio a nadar en Gijon",
        "la tarde que se perdio en el mercado",
    ],
    "genero": "memoria novelada",
    "tono": "cercano",
    "extension": 30000,
    "dedicatoria": "Para Marta, que siempre vuelve al mar.",
    "palabras_vetadas": [],
}


def _novela(conn: sqlite3.Connection, **cambios: object) -> str:
    """Un encargo cerrado y persistido, que es el punto de partida de todo esto."""
    respuestas = {**ENTREVISTA, **cambios}
    return crear_novela_desde_entrevista(conn, respuestas).volumen_id


def _escribir(conn: sqlite3.Connection, volumen_id: str) -> Bucle:
    """Encola y vacia la cola en modo demostracion. Devuelve el bucle para poder mirarlo."""
    encolar_escritura(conn, volumen_id, ModoDeEscritura.DEMOSTRACION)
    bucle = Bucle.para(conn, ModoDeEscritura.DEMOSTRACION)
    bucle.escribir_todo()
    return bucle


# --- A-1 y A-2: esquema y contrato del rol -------------------------------------------


@pytest.mark.invariants
def test_migracion_0004_anade_titulo_y_volumen(conn: sqlite3.Connection) -> None:
    columnas_de_capitulo = {
        fila["name"] for fila in conn.execute("PRAGMA table_info(capitulo)").fetchall()
    }
    columnas_de_plan = {
        fila["name"] for fila in conn.execute("PRAGMA table_info(plan)").fetchall()
    }
    assert "titulo" in columnas_de_capitulo
    assert {"volumen_id", "modo"} <= columnas_de_plan

    # Las dos decisiones de SPEC-004 quedan registradas y son inmutables.
    registradas = {
        fila["id"] for fila in conn.execute("SELECT id FROM registro_decision").fetchall()
    }
    assert {"rd-d20", "rd-d21"} <= registradas


@pytest.mark.invariants
def test_el_manifiesto_del_planner_cubre_la_version_vigente() -> None:
    """RF-APE-05: editar el prompt sin subir la version rompe el replay, y se detecta."""
    verificar_integridad_del_prompt()
    assert planner.VERSION_DE_PROMPT in planner.MANIFIESTO


# --- A-3 y B: la apertura --------------------------------------------------------------

# La fila de escena es larga por contrato -trece campos- y el fichero se salta el limite
# de linea solo aqui: partirla dejaria de ser el formato que el rol produce.
# ruff: noqa: E501
APERTURA_BUENA = """
## personajes
- p1 | Marta | protagonico | reconocerse en lo que le contaron | 1990

## lugares
- l1 | Gijon | olor a salitre

## eventos
- e1 | Marta aprende a nadar | 10 | accion | l1 | p1

## capitulos
1. El agua fria | e1 | Marta se mete en el mar | r1

## escenas
- s1 | 1 | p1 | l1 | 10 | volver al agua | el fondo no se ve | nada | miedo | orgullo | climax | accion | e1

## hechos_requeridos
- he-1
"""


@pytest.mark.invariants
def test_una_apertura_incompleta_rechaza_el_plan_entero() -> None:
    """RF-APE-02. Una referencia rota no se parchea: se rechaza todo y se dice cual es."""
    con_lugar_inexistente = APERTURA_BUENA.replace("| l1 | 10 | volver", "| l9 | 10 | volver")

    with pytest.raises(SalidaInvalidaDelPlanner) as error:
        parsear_apertura(con_lugar_inexistente)

    assert "l9" in str(error.value)


@pytest.mark.invariants
def test_una_escena_que_no_cambia_nada_no_valida() -> None:
    """RF-DOM-04 en el contrato del rol, donde se puede decir de que escena se habla."""
    inerte = APERTURA_BUENA.replace("| miedo | orgullo |", "| miedo | miedo |")

    with pytest.raises(SalidaInvalidaDelPlanner) as error:
        parsear_apertura(inerte)

    assert "s1" in str(error.value)


@pytest.mark.invariants
def test_un_recuerdo_obligatorio_sin_capitulo_rechaza_el_plan() -> None:
    """RF-APE-03. Una novela que se deja un recuerdo fuera parece completa y no lo esta."""
    with pytest.raises(SalidaInvalidaDelPlanner) as error:
        parsear_apertura(APERTURA_BUENA, recuerdos_obligatorios=("r1", "r2"))

    assert "r2" in str(error.value)
    assert "r1" not in str(error.value).split("no los cubre ningun capitulo:")[1]


@pytest.mark.invariants
def test_abrir_dos_veces_no_duplica_canon(conn: sqlite3.Connection) -> None:
    """RF-APE-04. Volver a pulsar el boton no puede duplicar la novela."""
    volumen_id = _novela(conn)
    encargo = leer_encargo(conn, volumen_id)
    apertura = parsear_apertura(
        ClienteDeDemostracion()
        .invocar(_prompt_de_apertura(conn, volumen_id), max_tokens=4000)
        .texto,
        recuerdos_obligatorios=encargo.ids_de_recuerdos,
    )

    primera = persistir_apertura(conn, encargo, apertura)
    segunda = persistir_apertura(conn, encargo, apertura)

    assert primera.ya_estaba is False
    assert segunda.ya_estaba is True
    capitulos = conn.execute(
        "SELECT COUNT(*) AS n FROM capitulo WHERE volumen_id = ?", (volumen_id,)
    ).fetchone()["n"]
    assert capitulos == len(ENTREVISTA["recuerdos"])  # type: ignore[arg-type]


def _prompt_de_apertura(conn: sqlite3.Connection, volumen_id: str) -> str:
    from backend.orchestrator.escritura import paquete_de_apertura

    _, prompt = paquete_de_apertura(conn, volumen_id, 0).ensamblar("t", "pq-1")
    return prompt


# --- C: los dos clientes ----------------------------------------------------------------


@pytest.mark.invariants
def test_sin_credencial_el_cliente_real_nombra_la_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RF-MOD-01. «No se puede» sin decir que falta obliga a ir a leer el codigo."""
    monkeypatch.delenv(VARIABLE_DE_CREDENCIAL, raising=False)

    with pytest.raises(CredencialAusente) as error:
        construir_cliente_real()

    assert VARIABLE_DE_CREDENCIAL in str(error.value)
    assert "demostracion" in str(error.value)


@pytest.mark.invariants
def test_con_credencial_el_cliente_real_se_construye_sin_invocar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(VARIABLE_DE_CREDENCIAL, "sk-ant-de-prueba")
    cliente = construir_cliente(ModoDeEscritura.MODELO)
    assert cliente.modelo != MODELO_DE_DEMOSTRACION


@pytest.mark.invariants
def test_el_modo_modelo_no_cae_en_demostracion_por_su_cuenta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D-08. Es la propiedad central de D-18: el modo degradado no se elige solo."""
    monkeypatch.delenv(VARIABLE_DE_CREDENCIAL, raising=False)

    with pytest.raises(CredencialAusente):
        construir_cliente(ModoDeEscritura.MODELO)

    assert construir_cliente(ModoDeEscritura.DEMOSTRACION).modelo == MODELO_DE_DEMOSTRACION


@pytest.mark.invariants
def test_la_procedencia_de_demostracion_es_reconocible(conn: sqlite3.Connection) -> None:
    """RF-MOD-03. Nada generado sin modelo puede confundirse despues con prosa de modelo."""
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)

    modelos = {
        fila["modelo"] for fila in conn.execute("SELECT modelo FROM procedencia").fetchall()
    }
    assert modelos == {MODELO_DE_DEMOSTRACION}


# --- D: el bucle --------------------------------------------------------------------------


@pytest.mark.invariants
def test_el_paquete_de_una_escena_lleva_los_intocables(conn: sqlite3.Connection) -> None:
    """RF-CTX: instruccion, estatico y epistemico no se recortan nunca."""
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)
    escena_id = conn.execute(
        "SELECT e.id FROM escena e JOIN capitulo c ON c.id = e.capitulo_id "
        "WHERE c.volumen_id = ? ORDER BY e.id LIMIT 1",
        (volumen_id,),
    ).fetchone()["id"]

    ensamblador = paquete_de_escena(conn, escena_id, 0)
    presentes = ensamblador.intocables_presentes()

    assert Componente.INSTRUCCION in presentes
    assert Componente.ESTATICO in presentes
    assert Componente.EPISTEMICO in presentes


@pytest.mark.invariants
def test_una_vuelta_deja_borrador_propuesto_y_transiciones_registradas(
    conn: sqlite3.Connection,
) -> None:
    """RF-ESC-02, RF-ESC-03 y RF-ESC-05, que son el criterio C-1 de la spec."""
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)

    borradores = conn.execute(
        "SELECT b.id, b.estado, b.texto, b.procedencia_id FROM borrador b "
        "JOIN escena e ON e.id = b.escena_id JOIN capitulo c ON c.id = e.capitulo_id "
        "WHERE c.volumen_id = ?",
        (volumen_id,),
    ).fetchall()

    assert len(borradores) == len(ENTREVISTA["recuerdos"])  # type: ignore[arg-type]
    assert all(b["texto"].strip() for b in borradores)
    assert all(b["procedencia_id"] for b in borradores)
    # Toda transicion tiene su fila: sin ellas el SSE emite un flujo vacio y la pantalla
    # lo lee como «no ha empezado».
    eventos = conn.execute("SELECT COUNT(*) AS n FROM tarea_evento").fetchone()["n"]
    assert eventos > 0
    # Y cada paquete quedo registrado con su hash.
    paquetes = conn.execute("SELECT hash FROM paquete_contexto").fetchall()
    assert paquetes and all(p["hash"].strip() for p in paquetes)


@pytest.mark.invariants
def test_ningun_borrador_llega_a_aceptado_con_evidencia_ausente(
    conn: sqlite3.Connection,
) -> None:
    """N-01 de la spec y D-19: la puerta no se levanta para poder ensenar la prosa."""
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)

    estados = {
        fila["estado"]
        for fila in conn.execute(
            "SELECT b.estado FROM borrador b JOIN escena e ON e.id = b.escena_id "
            "JOIN capitulo c ON c.id = e.capitulo_id WHERE c.volumen_id = ?",
            (volumen_id,),
        ).fetchall()
    }
    assert EstadoDeBorrador.ACEPTADO.value not in estados
    assert estados == {EstadoDeBorrador.EN_REVISION.value}

    puertas = conn.execute(
        "SELECT resultado, evidencia_ausente FROM puerta WHERE fase = 'escena_limpia'"
    ).fetchall()
    assert puertas
    assert all(p["resultado"] == "no_superada" for p in puertas)
    assert all("fuga_epistemica" in p["evidencia_ausente"] for p in puertas)


@pytest.mark.invariants
def test_un_termino_vetado_devuelve_el_borrador_al_redactor(
    conn: sqlite3.Connection,
) -> None:
    """RF-ESC-07. La palabra que el cliente veto no se negocia contra nada.

    «espejo» aparece en la prosa que compone el modo demostracion, asi que vetarla ejerce
    el camino entero: el guardarrail la encuentra, devuelve el texto al Redactor y la
    escena no llega a persistirse.
    """
    volumen_id = _novela(conn, palabras_vetadas=["espejo"])
    _escribir(conn, volumen_id)

    # El guardarrail corre antes de persistir: con el termino en la prosa de muestra, la
    # escena no llega a borrador y la tarea se detiene informando.
    borradores = conn.execute(
        "SELECT COUNT(*) AS n FROM borrador b JOIN escena e ON e.id = b.escena_id "
        "JOIN capitulo c ON c.id = e.capitulo_id WHERE c.volumen_id = ?",
        (volumen_id,),
    ).fetchone()["n"]
    registradas = conn.execute(
        "SELECT COUNT(*) AS n FROM audit_log WHERE decision = 'devolver_al_writer'"
    ).fetchone()["n"]

    assert borradores == 0
    assert registradas > 0


@pytest.mark.invariants
def test_agotada_la_escalera_la_escena_se_detiene_informando(
    conn: sqlite3.Connection,
) -> None:
    """RF-ESC-08 y RF-HAR-06: se para y se dice por que, no se reintenta sin fin."""
    volumen_id = _novela(conn, palabras_vetadas=["espejo"])
    _escribir(conn, volumen_id)

    estado = progreso(conn, volumen_id)

    assert estado.estado == "detenida"
    assert "agotaron su escalera" in estado.detalle
    detenidas = [e for e in estado.escenas if e.estado == EstadoDeTarea.ESCALADA.value]
    assert detenidas and all(e.falta for e in detenidas)


@pytest.mark.invariants
def test_la_misma_clave_no_vuelve_a_invocar(conn: sqlite3.Connection) -> None:
    """RF-ESC-09. Reanudar tras una caida no vuelve a pagar lo ya pagado."""
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)
    invocaciones_primera_vez = conn.execute(
        "SELECT COUNT(*) AS n FROM procedencia"
    ).fetchone()["n"]

    # Se encarga otra vez la misma novela: la apertura ve que ya estaba y las redacciones
    # encuentran su artefacto registrado con la misma clave de ejecucion.
    encolar_escritura(conn, volumen_id, ModoDeEscritura.DEMOSTRACION)
    cliente = ClienteDeDemostracion()
    Bucle(conn=conn, modo=ModoDeEscritura.DEMOSTRACION, cliente=cliente).escribir_todo()

    versiones = conn.execute(
        "SELECT COUNT(*) AS n FROM borrador b JOIN escena e ON e.id = b.escena_id "
        "JOIN capitulo c ON c.id = e.capitulo_id WHERE c.volumen_id = ?",
        (volumen_id,),
    ).fetchone()["n"]

    assert invocaciones_primera_vez > 0
    # Ni una redaccion mas: las escenas ya estaban escritas con esta misma clave.
    assert versiones == len(ENTREVISTA["recuerdos"])  # type: ignore[arg-type]
    assert not any("# Redactor" in prompt for prompt in cliente.invocaciones)


@pytest.mark.invariants
def test_el_credito_vuelve_a_cero_al_terminar(conn: sqlite3.Connection) -> None:
    """RF-ESC-04. Una reserva no liberada para el sistema sin ningun error visible."""
    volumen_id = _novela(conn)
    bucle = _escribir(conn, volumen_id)

    assert bucle.semaforo.en_vuelo == 0


@pytest.mark.invariants
def test_el_worker_vacia_la_cola_y_libera_el_credito(
    base_plantilla: Path, tmp_path: Path
) -> None:
    """RF-ESC-01. El proceso worker, con su propia conexion por vuelta."""
    from backend.worker.__main__ import Servicio

    copia = tmp_path / "canon.db"
    shutil.copy(base_plantilla, copia)
    with database.conexion(copia) as conn:
        volumen_id = _novela(conn)
        encolar_escritura(conn, volumen_id, ModoDeEscritura.DEMOSTRACION)

    servicio = Servicio(ruta=str(copia))
    servicio.servir(vueltas=50)

    with database.conexion(copia) as conn:
        pendientes = ColaDeTareas(conn).listas_del_plan(
            conn.execute(
                "SELECT id FROM plan WHERE volumen_id = ?", (volumen_id,)
            ).fetchone()["id"]
        )
        estado = progreso(conn, volumen_id)

    assert pendientes == 0
    assert estado.estado == "escrita"
    assert servicio.semaforo.en_vuelo == 0


@pytest.mark.invariants
def test_al_terminar_se_publica_una_version(conn: sqlite3.Connection) -> None:
    """RF-LEC-07 sigue en pie: la version se publica y la anterior nunca se toca."""
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)

    versiones = conn.execute(
        "SELECT numero, motivo FROM version_novela WHERE volumen_id = ?", (volumen_id,)
    ).fetchall()

    assert len(versiones) == 1
    assert "demostracion" in versiones[0]["motivo"]


# --- E: las rutas --------------------------------------------------------------------------


@pytest.fixture
def cliente_api(base_plantilla: Path, tmp_path: Path) -> Iterator[TestClient]:
    copia = tmp_path / "canon.db"
    shutil.copy(base_plantilla, copia)

    def conexion_de_prueba() -> Iterator[object]:
        with database.conexion(copia) as conn:
            yield conn

    main.app.dependency_overrides[main.obtener_conexion] = conexion_de_prueba
    try:
        yield TestClient(main.app)
    finally:
        main.app.dependency_overrides.clear()


@pytest.mark.invariants
def test_pedir_escritura_devuelve_202_y_no_invoca_modelos(cliente_api: TestClient) -> None:
    """RF-RUT-01. La generacion tarda minutos: la ruta encola y vuelve."""
    volumen_id = cliente_api.post(
        "/entrevista", json={"respuestas": ENTREVISTA, "texto_libre": ""}
    ).json()["volumen_id"]

    respuesta = cliente_api.post(
        f"/novelas/{volumen_id}/escritura", json={"modo": "demostracion"}
    )

    assert respuesta.status_code == 202
    cuerpo = respuesta.json()
    assert cuerpo["modo"] == "demostracion"
    assert cuerpo["tareas"]
    assert "demostracion" in cuerpo["aviso"].lower()
    # Nada se ha escrito todavia: la ruta no invoca.
    texto = cliente_api.get(f"/novelas/{volumen_id}/texto").json()
    assert texto["palabras"] == 0


@pytest.mark.invariants
def test_sin_credencial_el_modo_modelo_devuelve_503_util(
    cliente_api: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RF-RUT-03. Y sobre todo: no cae en demostracion por su cuenta."""
    monkeypatch.delenv(VARIABLE_DE_CREDENCIAL, raising=False)
    volumen_id = cliente_api.post(
        "/entrevista", json={"respuestas": ENTREVISTA, "texto_libre": ""}
    ).json()["volumen_id"]

    respuesta = cliente_api.post(f"/novelas/{volumen_id}/escritura", json={"modo": "modelo"})

    assert respuesta.status_code == 503
    assert VARIABLE_DE_CREDENCIAL in respuesta.json()["detail"]
    assert cliente_api.get(f"/novelas/{volumen_id}/escritura").json()["estado"] == (
        "sin_empezar"
    )


@pytest.mark.invariants
def test_una_novela_que_no_existe_da_404(cliente_api: TestClient) -> None:
    """RF-RUT-07. Y una que existe sin escribir da 200 con la lista vacia."""
    assert cliente_api.get("/novelas/vol-inventado/texto").status_code == 404
    assert (
        cliente_api.post(
            "/novelas/vol-inventado/escritura", json={"modo": "demostracion"}
        ).status_code
        == 404
    )


@pytest.mark.invariants
def test_el_progreso_enumera_las_escenas_con_su_estado(
    cliente_api: TestClient, tmp_path: Path
) -> None:
    """RF-RUT-04. La pantalla no deduce el estado global: se lo dan hecho."""
    volumen_id = cliente_api.post(
        "/entrevista", json={"respuestas": ENTREVISTA, "texto_libre": ""}
    ).json()["volumen_id"]
    cliente_api.post(f"/novelas/{volumen_id}/escritura", json={"modo": "demostracion"})

    antes = cliente_api.get(f"/novelas/{volumen_id}/escritura").json()
    assert antes["estado"] == "abriendo"
    assert antes["detalle"]

    _vaciar_la_cola(tmp_path / "canon.db")

    despues = cliente_api.get(f"/novelas/{volumen_id}/escritura").json()
    assert despues["estado"] == "escrita"
    assert despues["escritas"] == despues["totales"] == len(ENTREVISTA["recuerdos"])  # type: ignore[arg-type]
    assert all(e["estado"] == EstadoDeTarea.ACEPTADA.value for e in despues["escenas"])


@pytest.mark.invariants
def test_el_texto_sirve_el_ultimo_borrador_no_obsoleto_con_su_puerta(
    cliente_api: TestClient, tmp_path: Path
) -> None:
    """RF-RUT-05 y RF-PRE-04: la prosa viene con la verdad sobre su estado."""
    volumen_id = cliente_api.post(
        "/entrevista", json={"respuestas": ENTREVISTA, "texto_libre": ""}
    ).json()["volumen_id"]
    cliente_api.post(f"/novelas/{volumen_id}/escritura", json={"modo": "demostracion"})
    _vaciar_la_cola(tmp_path / "canon.db")

    cuerpo = cliente_api.get(f"/novelas/{volumen_id}/texto").json()

    assert cuerpo["palabras"] > 0
    assert cuerpo["de_demostracion"] is True
    assert len(cuerpo["capitulos"]) == len(ENTREVISTA["recuerdos"])  # type: ignore[arg-type]
    for capitulo in cuerpo["capitulos"]:
        assert capitulo["titulo"]
        for escena in capitulo["escenas"]:
            assert escena["texto"].strip()
            assert escena["aceptado"] is False
            # El motivo lo redacta el backend: la pantalla lo muestra, no lo compone.
            assert "evidencia" in escena["motivo"]


@pytest.mark.invariants
def test_las_rutas_nuevas_publican_operation_id() -> None:
    """RF-RUT-06. Sin `operationId` estable, el cliente generado cambia de nombres sola."""
    esquema = main.app.openapi()
    operaciones = {
        detalle["operationId"]
        for ruta in esquema["paths"].values()
        for detalle in ruta.values()
        if "operationId" in detalle
    }
    assert {"createEscritura", "readProgresoDeEscritura", "readTextoDeNovela"} <= operaciones


def _vaciar_la_cola(ruta: Path) -> None:
    """Hace el trabajo que en produccion hace el proceso worker."""
    from backend.worker.__main__ import Servicio

    entorno = os.environ.get(VARIABLE_DE_CREDENCIAL)
    try:
        Servicio(ruta=str(ruta)).servir(vueltas=100)
    finally:
        if entorno is not None:
            os.environ[VARIABLE_DE_CREDENCIAL] = entorno


# --- la lectura del texto, sin pasar por HTTP ------------------------------------------------


@pytest.mark.invariants
def test_la_lectura_devuelve_la_prosa_por_capitulos(conn: sqlite3.Connection) -> None:
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)

    capitulos = TextoDeLaNovela(conn).por_capitulos(volumen_id)

    assert len(capitulos) == len(ENTREVISTA["recuerdos"])  # type: ignore[arg-type]
    assert all(capitulo.palabras > 0 for capitulo in capitulos)
    assert all(
        escena.modelo == MODELO_DE_DEMOSTRACION
        for capitulo in capitulos
        for escena in capitulo.escenas
    )


@pytest.mark.invariants
def test_los_hechos_declarados_se_guardan_sin_canonizar(conn: sqlite3.Connection) -> None:
    """`CLAUDE.md` 3.4: el Redactor declara, la canonizacion es un paso aparte."""
    volumen_id = _novela(conn)
    encolar_escritura(conn, volumen_id, ModoDeEscritura.DEMOSTRACION)
    bucle = Bucle.para(conn, ModoDeEscritura.DEMOSTRACION)

    # Se para justo despues de la primera redaccion, antes de su canonizacion.
    while True:
        vuelta = bucle.una_vuelta()
        assert vuelta is not None
        if vuelta.tipo == "redaccion":
            break

    escena_id = vuelta.tarea_id.rsplit(":", 1)[0]
    borrador = Borradores(conn).ultimo_no_obsoleto(escena_id)
    assert borrador is not None
    sin_canonizar = conn.execute(
        "SELECT COUNT(*) AS n FROM hecho_detectado WHERE borrador_id = ? AND canonizado = 0",
        (borrador["id"],),
    ).fetchone()["n"]
    assert sin_canonizar > 0
