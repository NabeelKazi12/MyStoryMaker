"""La novela se aprueba: cierra el volumen, bloquea los cambios y se puede reabrir.

SPEC-007, PLAN-007. La firma de la persona es la evidencia `humano` de *promesa al
lector* en la puerta *Volumen cerrado*; lo determinista de esa puerta sigue bloqueando
aunque haya firma (N-02). Aprobar no cambia el estado de ningun borrador (N-01).

Cubre RF-APR-01 a RF-APR-11.
"""

from __future__ import annotations

import shutil
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import main
from backend.orchestrator.aprobacion import (
    AprobacionRechazada,
    NovelaAprobada,
    aprobar,
    exigir_abierta,
    retirar,
    vigente,
)
from backend.quality.puertas import volumen_cerrado
from backend.store import database
from tests.test_escritura import ENTREVISTA, _escribir, _novela, _vaciar_la_cola

# --- A-1: esquema ----------------------------------------------------------------------


@pytest.mark.invariants
def test_migracion_0005_crea_aprobacion_de_volumen(conn: sqlite3.Connection) -> None:
    columnas = {
        fila["name"]
        for fila in conn.execute("PRAGMA table_info(aprobacion_de_volumen)").fetchall()
    }
    assert {"id", "volumen_id", "version_id", "aprobada_en", "retirada_en"} <= columnas

    registradas = {
        fila["id"] for fila in conn.execute("SELECT id FROM registro_decision").fetchall()
    }
    assert "rd-d22" in registradas


# --- A-2: la firma como evidencia -------------------------------------------------------


@pytest.mark.invariants
def test_sin_firma_la_promesa_sigue_ausente() -> None:
    resultado = volumen_cerrado().evaluar([])

    assert "promesa_al_lector" in resultado.evidencia_ausente
    assert not resultado.superada


@pytest.mark.invariants
def test_la_firma_solo_retira_la_promesa() -> None:
    sin_firma = volumen_cerrado().evaluar([])
    con_firma = volumen_cerrado(firmada=True).evaluar([])

    assert set(sin_firma.evidencia_ausente) - set(con_firma.evidencia_ausente) == {
        "promesa_al_lector"
    }
    assert con_firma.politica is sin_firma.politica
    assert con_firma.superada


# --- B-1: orquestacion ------------------------------------------------------------------


@pytest.mark.invariants
def test_aprobar_registra_la_ultima_version(conn: sqlite3.Connection) -> None:
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)
    ultima = conn.execute(
        "SELECT id, numero FROM version_novela WHERE volumen_id = ? "
        "ORDER BY numero DESC LIMIT 1",
        (volumen_id,),
    ).fetchone()

    resultado = aprobar(conn, volumen_id)

    assert resultado.aprobacion.version_id == ultima["id"]
    assert resultado.aprobacion.version_numero == ultima["numero"]
    assert resultado.aprobacion.retirada_en is None
    # En v1 ningun borrador llega a aceptado: todos quedan firmados tal como estan.
    escenas = conn.execute(
        "SELECT COUNT(*) FROM escena e JOIN capitulo c ON c.id = e.capitulo_id "
        "WHERE c.volumen_id = ?",
        (volumen_id,),
    ).fetchone()[0]
    assert resultado.sin_aceptar == escenas
    assert vigente(conn, volumen_id) == resultado.aprobacion

    puerta = conn.execute(
        "SELECT fase, resultado, evidencia_ausente FROM puerta WHERE ambito_id = ?",
        (volumen_id,),
    ).fetchone()
    assert puerta["fase"] == "volumen_cerrado"
    assert puerta["resultado"] == "superada"
    assert puerta["evidencia_ausente"] == ""


@pytest.mark.invariants
def test_aprobar_no_cambia_ningun_borrador(conn: sqlite3.Connection) -> None:
    """N-01: la aprobacion es del volumen, no de sus escenas."""
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)
    antes = conn.execute("SELECT id, estado FROM borrador ORDER BY id").fetchall()

    aprobar(conn, volumen_id)

    despues = conn.execute("SELECT id, estado FROM borrador ORDER BY id").fetchall()
    assert [tuple(f) for f in antes] == [tuple(f) for f in despues]


@pytest.mark.invariants
def test_una_siembra_abierta_impide_aprobar(conn: sqlite3.Connection) -> None:
    """RF-APR-04 y N-02: lo determinista bloquea aunque haya firma."""
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)
    escena = conn.execute(
        "SELECT e.id FROM escena e JOIN capitulo c ON c.id = e.capitulo_id "
        "WHERE c.volumen_id = ? LIMIT 1",
        (volumen_id,),
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO siembra_pago (id, tipo, escena_siembra, estado) "
        "VALUES ('sp-1', 'objeto', ?, 'abierto')",
        (escena,),
    )

    with pytest.raises(AprobacionRechazada) as rechazo:
        aprobar(conn, volumen_id)

    assert rechazo.value.defectos
    assert "sp-1" in rechazo.value.defectos[0].evidencia
    assert vigente(conn, volumen_id) is None
    assert conn.execute("SELECT COUNT(*) FROM aprobacion_de_volumen").fetchone()[0] == 0
    puerta = conn.execute(
        "SELECT resultado FROM puerta WHERE ambito_id = ?", (volumen_id,)
    ).fetchone()
    assert puerta["resultado"] == "no_superada"


@pytest.mark.invariants
def test_la_siembra_de_otra_novela_no_bloquea_esta(conn: sqlite3.Connection) -> None:
    """La puerta mira el canon de **este** volumen; con dos en la base no se mezclan."""
    otra = _novela(conn, nombre="Ana")
    _escribir(conn, otra)
    escena_ajena = conn.execute(
        "SELECT e.id FROM escena e JOIN capitulo c ON c.id = e.capitulo_id "
        "WHERE c.volumen_id = ? LIMIT 1",
        (otra,),
    ).fetchone()["id"]
    conn.execute(
        "INSERT INTO siembra_pago (id, tipo, escena_siembra, estado) "
        "VALUES ('sp-ajena', 'objeto', ?, 'abierto')",
        (escena_ajena,),
    )
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)

    assert aprobar(conn, volumen_id).aprobacion.volumen_id == volumen_id


@pytest.mark.invariants
def test_sin_terminar_no_se_aprueba_y_se_dice_por_que(conn: sqlite3.Connection) -> None:
    """RF-APR-01."""
    volumen_id = _novela(conn)

    with pytest.raises(AprobacionRechazada) as rechazo:
        aprobar(conn, volumen_id)

    assert "sin_empezar" in str(rechazo.value)
    assert "todavia no se ha encargado" in str(rechazo.value)


@pytest.mark.invariants
def test_aprobar_dos_veces_no_duplica(conn: sqlite3.Connection) -> None:
    """RF-APR-06."""
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)
    aprobar(conn, volumen_id)

    with pytest.raises(AprobacionRechazada):
        aprobar(conn, volumen_id)

    assert conn.execute("SELECT COUNT(*) FROM aprobacion_de_volumen").fetchone()[0] == 1


@pytest.mark.invariants
def test_retirar_no_borra_la_aprobacion(conn: sqlite3.Connection) -> None:
    """RF-APR-07."""
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)
    aprobada = aprobar(conn, volumen_id).aprobacion

    retirada = retirar(conn, volumen_id)

    assert retirada.id == aprobada.id
    assert retirada.retirada_en is not None
    assert vigente(conn, volumen_id) is None
    assert conn.execute("SELECT COUNT(*) FROM aprobacion_de_volumen").fetchone()[0] == 1
    # Reabierta, se puede volver a aprobar, y la primera sigue en el historial.
    aprobar(conn, volumen_id)
    assert conn.execute("SELECT COUNT(*) FROM aprobacion_de_volumen").fetchone()[0] == 2


@pytest.mark.invariants
def test_retirar_sin_aprobacion_se_rechaza(conn: sqlite3.Connection) -> None:
    volumen_id = _novela(conn)

    with pytest.raises(AprobacionRechazada):
        retirar(conn, volumen_id)


@pytest.mark.invariants
def test_aprobar_y_retirar_quedan_en_audit_log(conn: sqlite3.Connection) -> None:
    """RF-APR-10."""
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)
    aprobar(conn, volumen_id)
    retirar(conn, volumen_id)

    decisiones = [
        fila["decision"]
        for fila in conn.execute(
            "SELECT decision FROM audit_log WHERE ambito = 'aprobacion' ORDER BY rowid"
        ).fetchall()
    ]
    assert decisiones == ["aprobar_volumen", "retirar_aprobacion"]


@pytest.mark.invariants
def test_exigir_abierta_para_la_novela_aprobada(conn: sqlite3.Connection) -> None:
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)
    exigir_abierta(conn, volumen_id)

    aprobar(conn, volumen_id)

    with pytest.raises(NovelaAprobada, match="reábrela"):
        exigir_abierta(conn, volumen_id)


# --- B-2: invariante --------------------------------------------------------------------


@pytest.mark.invariants
def test_invariante_las_aprobaciones_no_se_pierden(conn: sqlite3.Connection) -> None:
    """RF-APR-07: la tabla no pierde filas. La base lo impide, no la disciplina."""
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)
    aprobar(conn, volumen_id)

    with pytest.raises(sqlite3.DatabaseError):
        conn.execute("DELETE FROM aprobacion_de_volumen")

    assert conn.execute("SELECT COUNT(*) FROM aprobacion_de_volumen").fetchone()[0] == 1


@pytest.mark.invariants
def test_invariante_una_sola_aprobacion_vigente(conn: sqlite3.Connection) -> None:
    volumen_id = _novela(conn)
    _escribir(conn, volumen_id)
    aprobada = aprobar(conn, volumen_id).aprobacion

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO aprobacion_de_volumen (id, volumen_id, version_id, aprobada_en) "
            "VALUES ('apr-otra', ?, ?, datetime('now'))",
            (volumen_id, aprobada.version_id),
        )


# --- C: las rutas -----------------------------------------------------------------------


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


def _novela_escrita(cliente: TestClient, ruta: Path) -> str:
    volumen_id = str(
        cliente.post("/entrevista", json={"respuestas": ENTREVISTA, "texto_libre": ""}).json()[
            "volumen_id"
        ]
    )
    cliente.post(f"/novelas/{volumen_id}/escritura", json={"modo": "demostracion"})
    _vaciar_la_cola(ruta)
    return volumen_id


@pytest.mark.invariants
def test_aprobar_sin_terminar_devuelve_409_con_el_detalle(cliente: TestClient) -> None:
    volumen_id = cliente.post(
        "/entrevista", json={"respuestas": ENTREVISTA, "texto_libre": ""}
    ).json()["volumen_id"]

    respuesta = cliente.post(f"/novelas/{volumen_id}/aprobacion")

    assert respuesta.status_code == 409
    assert "todavia no se ha encargado" in respuesta.json()["detail"]["motivo"]


@pytest.mark.invariants
def test_aprobar_por_la_ruta_devuelve_201_y_la_lectura_la_trae(
    cliente: TestClient, ruta: Path
) -> None:
    """RF-APR-05, RF-APR-09."""
    volumen_id = _novela_escrita(cliente, ruta)
    assert cliente.get(f"/novelas/{volumen_id}/lectura").json()["aprobacion"] is None

    respuesta = cliente.post(f"/novelas/{volumen_id}/aprobacion")

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["aprobacion"]["version_numero"] == 1
    assert cuerpo["sin_aceptar"] > 0
    lectura = cliente.get(f"/novelas/{volumen_id}/lectura").json()
    assert lectura["aprobacion"] == cuerpo["aprobacion"]


@pytest.mark.invariants
def test_aprobar_dos_veces_devuelve_409(cliente: TestClient, ruta: Path) -> None:
    volumen_id = _novela_escrita(cliente, ruta)
    cliente.post(f"/novelas/{volumen_id}/aprobacion")

    assert cliente.post(f"/novelas/{volumen_id}/aprobacion").status_code == 409


@pytest.mark.invariants
def test_una_siembra_abierta_devuelve_409_con_los_defectos(
    cliente: TestClient, ruta: Path
) -> None:
    volumen_id = _novela_escrita(cliente, ruta)
    with database.conexion(ruta) as conn:
        escena = conn.execute(
            "SELECT e.id FROM escena e JOIN capitulo c ON c.id = e.capitulo_id "
            "WHERE c.volumen_id = ? LIMIT 1",
            (volumen_id,),
        ).fetchone()["id"]
        conn.execute(
            "INSERT INTO siembra_pago (id, tipo, escena_siembra, estado) "
            "VALUES ('sp-1', 'objeto', ?, 'abierto')",
            (escena,),
        )

    respuesta = cliente.post(f"/novelas/{volumen_id}/aprobacion")

    assert respuesta.status_code == 409
    defectos = respuesta.json()["detail"]["defectos"]
    assert defectos and "sp-1" in defectos[0]["evidencia"]


@pytest.mark.invariants
def test_una_novela_aprobada_no_se_reescribe_ni_se_retitula(
    cliente: TestClient, ruta: Path
) -> None:
    """RF-APR-08, y tras reabrir todo vuelve a estar permitido."""
    volumen_id = _novela_escrita(cliente, ruta)
    cliente.post(f"/novelas/{volumen_id}/aprobacion")

    escritura = cliente.post(f"/novelas/{volumen_id}/escritura", json={"modo": "demostracion"})
    cambio = cliente.post(
        f"/novelas/{volumen_id}/cambios", json={"hecho_id": "h-1", "descripcion": "otro"}
    )
    portada = cliente.patch(f"/novelas/{volumen_id}/portada", json={"titulo": "Otro"})

    for respuesta in (escritura, cambio, portada):
        assert respuesta.status_code == 409
        assert "reábrela" in respuesta.json()["detail"]
    assert cliente.get(f"/novelas/{volumen_id}/lectura").json()["titulo"] != "Otro"

    retirada = cliente.post(f"/novelas/{volumen_id}/aprobacion/retirada")
    assert retirada.status_code == 200
    assert retirada.json()["aprobacion"]["retirada_en"] is not None
    assert cliente.get(f"/novelas/{volumen_id}/lectura").json()["aprobacion"] is None
    assert (
        cliente.patch(f"/novelas/{volumen_id}/portada", json={"titulo": "Otro"}).status_code
        == 200
    )


@pytest.mark.invariants
def test_retirar_sin_aprobacion_devuelve_409(cliente: TestClient, ruta: Path) -> None:
    volumen_id = _novela_escrita(cliente, ruta)

    assert cliente.post(f"/novelas/{volumen_id}/aprobacion/retirada").status_code == 409


@pytest.mark.invariants
def test_volumen_inexistente_404(cliente: TestClient) -> None:
    """RF-APR-11."""
    # El motivo se comprueba: un 404 de «ruta desconocida» tambien es un 404.
    base = "/novelas/vol-no-existe/aprobacion"
    for ruta in (base, f"{base}/retirada"):
        respuesta = cliente.post(ruta)
        assert respuesta.status_code == 404
        assert "no existe el volumen" in respuesta.json()["detail"]


@pytest.mark.invariants
def test_las_rutas_de_aprobacion_publican_operation_id() -> None:
    esquema = main.app.openapi()
    operaciones = {
        detalle["operationId"]
        for ruta in esquema["paths"].values()
        for detalle in ruta.values()
        if "operationId" in detalle
    }
    assert {"createAprobacion", "createRetiradaDeAprobacion"} <= operaciones
