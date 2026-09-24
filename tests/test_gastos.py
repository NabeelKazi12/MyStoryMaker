"""Gastos y trazas: lo que cuesta cada novela, desde SQLite, y cada llamada en Langfuse.

SPEC-012, PLAN-010. SQLite es la fuente de verdad (SPEC-003 S-02): la pestaña de gastos
se lee de ahi, y Langfuse es la vista. El cliente de Langfuse se prueba contra un
transporte HTTP falso: la suite no necesita red ni claves.

Cubre RF-GAS-01 a RF-GAS-07 y RF-LAN-01 a RF-LAN-05.
"""

from __future__ import annotations

import base64
import dataclasses
import json
import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import main
from backend.domain.vocabularies import ModoDeEscritura
from backend.observability.langfuse import (
    ClienteLangfuse,
    LlamadaObservada,
    cliente_desde_el_entorno,
    langfuse_activo,
    registrar_llamada,
    url_de_traza,
)
from backend.observability.trazas import ClienteFalsoDeObservabilidad, ClienteNulo
from backend.orchestrator.escritura import encolar_escritura
from backend.store import database
from backend.store.gastos import GastosDeLaNovela
from backend.worker.bucle import Bucle
from tests.test_escritura import ENTREVISTA, _escribir, _novela

# --- A-1 y A-2: los tokens se guardan ---------------------------------------------------


@pytest.mark.invariants
def test_migracion_0007_anade_tokens_a_la_procedencia(conn: sqlite3.Connection) -> None:
    columnas = {f["name"] for f in conn.execute("PRAGMA table_info(procedencia)").fetchall()}
    assert {"tokens_entrada", "tokens_salida"} <= columnas
    registradas = {f["id"] for f in conn.execute("SELECT id FROM registro_decision").fetchall()}
    assert "rd-d24" in registradas


@pytest.mark.invariants
def test_cada_procedencia_nueva_lleva_sus_tokens(conn: sqlite3.Connection) -> None:
    """RF-GAS-02: el cliente de demostracion devuelve tokens y la procedencia los guarda."""
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)

    filas = conn.execute("SELECT tokens_entrada, tokens_salida FROM procedencia").fetchall()

    assert filas
    assert all(f["tokens_entrada"] and f["tokens_entrada"] > 0 for f in filas)
    assert all(f["tokens_salida"] and f["tokens_salida"] > 0 for f in filas)


# --- B-1: la lectura de gastos ----------------------------------------------------------


@pytest.mark.invariants
def test_los_gastos_de_una_novela_no_mezclan_otra(conn: sqlite3.Connection) -> None:
    """RF-GAS-05."""
    una = _novela(conn, nombre="Ana")
    _escribir(conn, una)
    otra = _novela(conn)
    _escribir(conn, otra)

    de_una = GastosDeLaNovela(conn).llamadas(una)
    de_otra = GastosDeLaNovela(conn).llamadas(otra)
    total = conn.execute("SELECT COUNT(*) FROM procedencia").fetchone()[0]

    assert de_una and de_otra
    assert not {ll.id for ll in de_una} & {ll.id for ll in de_otra}
    assert len(de_una) + len(de_otra) == total


@pytest.mark.invariants
def test_el_total_es_la_suma_de_las_llamadas(conn: sqlite3.Connection) -> None:
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)
    conn.execute("UPDATE procedencia SET coste = 0.25")

    resumen = GastosDeLaNovela(conn).resumen(volumen_id)

    assert resumen.total.llamadas == len(resumen.llamadas)
    assert resumen.total.coste == pytest.approx(0.25 * len(resumen.llamadas))
    assert resumen.total.tokens_salida == sum(ll.tokens_salida or 0 for ll in resumen.llamadas)
    assert sum(r.coste for r in resumen.por_rol) == pytest.approx(resumen.total.coste)
    assert {r.nombre for r in resumen.por_rol} == {ll.agente for ll in resumen.llamadas}
    capitulos = [ll for ll in resumen.llamadas if ll.capitulo_orden is not None]
    assert sum(c.llamadas for c in resumen.por_capitulo) == len(capitulos)


@pytest.mark.invariants
def test_las_llamadas_antiguas_sin_tokens_se_cuentan_aparte(conn: sqlite3.Connection) -> None:
    """N-05: una fila de antes de `0007` no tiene tokens; no suma, pero se dice."""
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)
    conn.execute(
        "UPDATE procedencia SET tokens_entrada = NULL, tokens_salida = NULL "
        "WHERE rowid = (SELECT MIN(rowid) FROM procedencia)"
    )

    resumen = GastosDeLaNovela(conn).resumen(volumen_id)

    assert resumen.total.llamadas_sin_tokens == 1


@pytest.mark.invariants
def test_cada_llamada_sabe_su_capitulo_e_intento(conn: sqlite3.Connection) -> None:
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)

    llamadas = GastosDeLaNovela(conn).llamadas(volumen_id)

    apertura = [ll for ll in llamadas if ll.tarea == "apertura"]
    redaccion = [ll for ll in llamadas if ll.tarea == "redaccion"]
    assert apertura and redaccion
    assert all(ll.escena_id is None and ll.capitulo_orden is None for ll in apertura)
    assert all(ll.escena_id and ll.capitulo_orden for ll in redaccion)
    assert {ll.intento for ll in apertura} == set(range(1, len(apertura) + 1))
    momentos = [ll.momento for ll in llamadas]
    assert momentos == sorted(momentos)


# --- B-2: la ruta -----------------------------------------------------------------------


@pytest.fixture
def ruta(base_plantilla: Path, tmp_path: Path) -> Path:
    copia = tmp_path / "canon.db"
    shutil.copy(base_plantilla, copia)
    return copia


@pytest.fixture
def cliente(ruta: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    for variable in (
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_HOST",
        "LANGFUSE_PROJECT_ID",
    ):
        monkeypatch.delenv(variable, raising=False)

    def conexion_de_prueba() -> Iterator[object]:
        with database.conexion(ruta) as conn:
            yield conn

    main.app.dependency_overrides[main.obtener_conexion] = conexion_de_prueba
    try:
        yield TestClient(main.app)
    finally:
        main.app.dependency_overrides.clear()


def _novela_por_la_ruta(cliente: TestClient) -> str:
    respuesta = cliente.post("/entrevista", json={"respuestas": ENTREVISTA, "texto_libre": ""})
    return str(respuesta.json()["volumen_id"])


@pytest.mark.invariants
def test_sin_llamadas_los_gastos_son_cero(cliente: TestClient) -> None:
    """RF-GAS-06."""
    volumen_id = _novela_por_la_ruta(cliente)

    respuesta = cliente.get(f"/novelas/{volumen_id}/gastos")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["moneda"] == "USD"
    assert cuerpo["total"]["llamadas"] == 0
    assert cuerpo["total"]["coste"] == 0
    assert cuerpo["llamadas"] == [] and cuerpo["por_rol"] == [] and cuerpo["por_capitulo"] == []
    assert cuerpo["langfuse_activo"] is False


@pytest.mark.invariants
def test_la_ruta_sirve_las_llamadas_con_sus_campos(cliente: TestClient, ruta: Path) -> None:
    """RF-GAS-03, RF-GAS-04; sin Langfuse, ninguna traza_url."""
    from tests.test_escritura import _vaciar_la_cola

    volumen_id = _novela_por_la_ruta(cliente)
    cliente.post(f"/novelas/{volumen_id}/escritura", json={"modo": "demostracion"})
    _vaciar_la_cola(ruta)

    cuerpo = cliente.get(f"/novelas/{volumen_id}/gastos").json()

    assert cuerpo["total"]["llamadas"] == len(cuerpo["llamadas"]) > 0
    campos = {
        "id",
        "momento",
        "agente",
        "modelo",
        "version_de_prompt",
        "tarea",
        "escena_id",
        "capitulo_orden",
        "intento",
        "coste",
        "latencia_ms",
        "tokens_entrada",
        "tokens_salida",
        "clase_de_fallo",
        "traza_url",
    }
    assert all(set(ll) == campos for ll in cuerpo["llamadas"])
    assert all(ll["traza_url"] is None for ll in cuerpo["llamadas"])
    assert set(cuerpo["total"]) == {
        "coste",
        "llamadas",
        "fallidas",
        "tokens_entrada",
        "tokens_salida",
        "latencia_ms",
        "llamadas_sin_tokens",
    }


@pytest.mark.invariants
def test_pedir_los_gastos_no_escribe_nada(cliente: TestClient, ruta: Path) -> None:
    """RF-GAS-07."""
    volumen_id = _novela_por_la_ruta(cliente)

    def cuentas() -> tuple[int, ...]:
        with database.conexion(ruta) as conn:
            return tuple(
                conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("procedencia", "tarea", "audit_log", "puerta")
            )

    antes = cuentas()
    assert cliente.get(f"/novelas/{volumen_id}/gastos").status_code == 200
    assert cuentas() == antes


@pytest.mark.invariants
def test_la_ruta_publica_read_gastos() -> None:
    esquema = main.app.openapi()
    operaciones = {
        detalle["operationId"]
        for ruta in esquema["paths"].values()
        for detalle in ruta.values()
        if "operationId" in detalle
    }
    assert "readGastos" in operaciones


# --- C-1: el cliente de Langfuse --------------------------------------------------------


@dataclasses.dataclass
class TransporteFalso:
    """Registra cada peticion y contesta lo que se le diga. Nada sale a la red."""

    estado: int = 207
    lanza: Exception | None = None
    peticiones: list[tuple[str, str, dict[str, str], bytes | None]] = dataclasses.field(
        default_factory=list
    )

    def __call__(
        self,
        metodo: str,
        url: str,
        cabeceras: dict[str, str],
        cuerpo: bytes | None,
        espera: float,
    ) -> tuple[int, bytes]:
        self.peticiones.append((metodo, url, cabeceras, cuerpo))
        if self.lanza is not None:
            raise self.lanza
        return self.estado, b'{"successes": [], "errors": []}'

    def lotes(self) -> list[list[dict[str, object]]]:
        return [
            json.loads(cuerpo)["batch"]
            for metodo, url, _, cuerpo in self.peticiones
            if url.endswith("/api/public/ingestion") and cuerpo is not None
        ]


LLAMADA = LlamadaObservada(
    procedencia_id="pr-abc",
    volumen_id="vol-1",
    agente="redactor",
    tarea="redaccion",
    modelo="claude-haiku-4-5",
    version_de_prompt="1.1.0",
    tokens_entrada=1200,
    tokens_salida=800,
    coste=0.0123,
    latencia_ms=4200,
    clase_de_fallo=None,
    escena_id="esc-1",
    capitulo_orden=2,
    modo="modelo",
)


def _cliente(transporte: TransporteFalso) -> ClienteLangfuse:
    return ClienteLangfuse(
        host="https://langfuse.ejemplo",
        clave_publica="pk-lf-dummy",
        clave_secreta="sk-lf-dummy",
        transporte=transporte,
    )


@pytest.mark.invariants
def test_una_llamada_es_una_traza_en_la_sesion_de_su_novela() -> None:
    """RF-LAN-02."""
    transporte = TransporteFalso()

    registrar_llamada(_cliente(transporte), LLAMADA)

    (lote,) = transporte.lotes()
    tipos = [evento["type"] for evento in lote]
    assert tipos == ["trace-create", "generation-create"]
    traza = lote[0]["body"]
    assert isinstance(traza, dict)
    assert traza["id"] == "pr-abc"
    assert traza["sessionId"] == "vol-1"
    assert traza["name"] == "redactor:redaccion"
    generacion = lote[1]["body"]
    assert isinstance(generacion, dict)
    assert generacion["traceId"] == "pr-abc"
    assert generacion["model"] == "claude-haiku-4-5"
    assert generacion["usageDetails"] == {"input": 1200, "output": 800}
    assert generacion["costDetails"] == {"total": 0.0123}
    assert generacion["metadata"]["version_de_prompt"] == "1.1.0"  # type: ignore[index]
    assert generacion["metadata"]["capitulo_orden"] == "2"  # type: ignore[index]
    assert "level" not in generacion or generacion["level"] == "DEFAULT"
    _, url, cabeceras, _ = transporte.peticiones[-1]
    assert url == "https://langfuse.ejemplo/api/public/ingestion"
    esperado = base64.b64encode(b"pk-lf-dummy:sk-lf-dummy").decode()
    assert cabeceras["Authorization"] == f"Basic {esperado}"


@pytest.mark.invariants
def test_una_llamada_fallida_va_con_nivel_error() -> None:
    transporte = TransporteFalso()

    registrar_llamada(
        _cliente(transporte), dataclasses.replace(LLAMADA, clase_de_fallo="contrato")
    )

    generacion = transporte.lotes()[0][1]["body"]
    assert isinstance(generacion, dict)
    assert generacion["level"] == "ERROR"
    assert "contrato" in str(generacion["statusMessage"])


@pytest.mark.invariants
def test_el_lote_no_lleva_prosa() -> None:
    """RF-LAN-04: ni texto, ni prompt, ni paquete: solo lo de RF-LAN-02."""
    transporte = TransporteFalso()

    registrar_llamada(_cliente(transporte), LLAMADA)

    for evento in transporte.lotes()[0]:
        cuerpo = evento["body"]
        assert isinstance(cuerpo, dict)
        assert not {"input", "output", "prompt", "texto"} & set(cuerpo)


@pytest.mark.invariants
def test_sin_variables_el_cliente_es_nulo() -> None:
    """RF-LAN-01."""
    completas = {
        "LANGFUSE_PUBLIC_KEY": "pk-lf-dummy",
        "LANGFUSE_SECRET_KEY": "sk-lf-dummy",
        "LANGFUSE_HOST": "https://langfuse.ejemplo",
    }
    transporte = TransporteFalso()
    assert isinstance(cliente_desde_el_entorno(completas, transporte), ClienteLangfuse)
    for falta in completas:
        incompletas = {k: v for k, v in completas.items() if k != falta}
        assert isinstance(cliente_desde_el_entorno(incompletas, transporte), ClienteNulo)
    # Los valores de ejemplo de `.env.example` tampoco activan nada.
    ejemplo = {**completas, "LANGFUSE_PUBLIC_KEY": "pk-lf-TU_CLAVE_AQUI"}
    assert isinstance(cliente_desde_el_entorno(ejemplo, transporte), ClienteNulo)


@pytest.mark.invariants
@pytest.mark.parametrize(
    "transporte",
    [
        TransporteFalso(estado=500),
        TransporteFalso(estado=401),
        TransporteFalso(lanza=TimeoutError()),
    ],
    ids=["500", "401", "tiempo-agotado"],
)
def test_un_fallo_al_enviar_no_se_propaga(transporte: TransporteFalso) -> None:
    """RF-LAN-03."""
    registrar_llamada(_cliente(transporte), LLAMADA)  # no lanza

    assert transporte.peticiones


@pytest.mark.invariants
def test_la_url_de_la_traza_necesita_el_proyecto() -> None:
    """RF-LAN-05, con la desviacion DV-1: el proyecto sale del entorno, no de la red.

    `api/` y `observability/` no pueden hacer HTTP (`test_import_boundaries`), asi que el
    enlace se compone sin preguntar a Langfuse.
    """
    entorno = {
        "LANGFUSE_PUBLIC_KEY": "pk-lf-dummy",
        "LANGFUSE_SECRET_KEY": "sk-lf-dummy",
        "LANGFUSE_HOST": "https://langfuse.ejemplo/",
        "LANGFUSE_PROJECT_ID": "proyecto-1",
    }
    assert url_de_traza(entorno, "pr-abc") == (
        "https://langfuse.ejemplo/project/proyecto-1/traces/pr-abc"
    )
    sin_proyecto = {k: v for k, v in entorno.items() if k != "LANGFUSE_PROJECT_ID"}
    assert url_de_traza(sin_proyecto, "pr-abc") is None
    sin_claves = {k: v for k, v in entorno.items() if k != "LANGFUSE_SECRET_KEY"}
    assert url_de_traza(sin_claves, "pr-abc") is None
    de_ejemplo = {**entorno, "LANGFUSE_PROJECT_ID": "TU_PROYECTO_AQUI"}
    assert url_de_traza(de_ejemplo, "pr-abc") is None
    assert langfuse_activo(entorno) and not langfuse_activo(sin_claves)


# --- C-2: el worker envia cada llamada --------------------------------------------------


@pytest.mark.invariants
def test_el_bucle_envia_cada_llamada_al_observador(conn: sqlite3.Connection) -> None:
    volumen_id = _novela(conn)
    encolar_escritura(conn, volumen_id, ModoDeEscritura.DEMOSTRACION)
    doble = ClienteFalsoDeObservabilidad()
    bucle = dataclasses.replace(
        Bucle.para(conn, ModoDeEscritura.DEMOSTRACION), observabilidad=doble
    )

    bucle.escribir_todo()

    procedencias = {f["id"] for f in conn.execute("SELECT id FROM procedencia").fetchall()}
    assert {t.id for t in doble.trazas} == procedencias
    assert all(t.sesion == volumen_id and t.terminada for t in doble.trazas)
    assert {s.traza_id for s in doble.spans} == procedencias
    assert all(s.uso is not None and s.uso.tokens_salida > 0 for s in doble.spans)
    assert all(s.version_de_prompt for s in doble.spans)


@pytest.mark.invariants
def test_con_langfuse_cada_llamada_enlaza_a_su_traza(
    cliente: TestClient, ruta: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RF-LAN-05 por la ruta: el id de la traza es el de la procedencia."""
    from tests.test_escritura import _vaciar_la_cola

    volumen_id = _novela_por_la_ruta(cliente)
    cliente.post(f"/novelas/{volumen_id}/escritura", json={"modo": "demostracion"})
    _vaciar_la_cola(ruta)
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-dummy")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-dummy")
    monkeypatch.setenv("LANGFUSE_HOST", "https://langfuse.ejemplo")
    monkeypatch.setenv("LANGFUSE_PROJECT_ID", "proyecto-1")

    cuerpo = cliente.get(f"/novelas/{volumen_id}/gastos").json()

    assert cuerpo["langfuse_activo"] is True
    for llamada in cuerpo["llamadas"]:
        assert llamada["traza_url"] == (
            f"https://langfuse.ejemplo/project/proyecto-1/traces/{llamada['id']}"
        )


@pytest.mark.invariants
def test_una_llamada_anterior_a_langfuse_no_enlaza(
    cliente: TestClient, ruta: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DV-3: sin tokens, la llamada es de antes de SPEC-012 y nunca se envio (N-06)."""
    from tests.test_escritura import _vaciar_la_cola

    volumen_id = _novela_por_la_ruta(cliente)
    cliente.post(f"/novelas/{volumen_id}/escritura", json={"modo": "demostracion"})
    _vaciar_la_cola(ruta)
    with database.conexion(ruta) as conn:
        antigua = conn.execute("SELECT id FROM procedencia ORDER BY rowid LIMIT 1").fetchone()[
            "id"
        ]
        conn.execute(
            "UPDATE procedencia SET tokens_entrada = NULL, tokens_salida = NULL WHERE id = ?",
            (antigua,),
        )
    for nombre, valor in (
        ("LANGFUSE_PUBLIC_KEY", "pk-lf-dummy"),
        ("LANGFUSE_SECRET_KEY", "sk-lf-dummy"),
        ("LANGFUSE_HOST", "https://langfuse.ejemplo"),
        ("LANGFUSE_PROJECT_ID", "proyecto-1"),
    ):
        monkeypatch.setenv(nombre, valor)

    llamadas = {
        ll["id"]: ll for ll in cliente.get(f"/novelas/{volumen_id}/gastos").json()["llamadas"]
    }

    assert llamadas[antigua]["traza_url"] is None
    assert all(ll["traza_url"] for i, ll in llamadas.items() if i != antigua)
